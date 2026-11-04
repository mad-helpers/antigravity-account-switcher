#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Antigravity Migration & Transfer Engine
Author: Madgod-xyz (https://github.com/Madgod-xyz/antigravity-account-switcher)
Description:
    Safely inspects, clones, migrates, and syncs Antigravity project conversations,
    workspaces, and agent brains between different Google accounts.
    Includes robust Scheduled Tasks isolation and granular project profile assignment.
"""

import os
import sys
import glob
import json
import uuid
import time
import shutil
import sqlite3
import datetime
import subprocess
import urllib.parse
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

GEMINI_DIR = os.path.expanduser('~/.gemini')
ANTIGRAVITY_DIR = os.path.join(GEMINI_DIR, 'antigravity')
CONVERSATIONS_DIR = os.path.join(ANTIGRAVITY_DIR, 'conversations')
BRAIN_DIR = os.path.join(ANTIGRAVITY_DIR, 'brain')
ACCOUNTS_DIR = os.path.join(GEMINI_DIR, 'accounts')
BACKUP_DIR = os.path.join(GEMINI_DIR, 'antigravity-backup')
CONFIG_PROJECTS_DIR = os.path.join(GEMINI_DIR, 'config', 'projects')
CONVERSATION_SUMMARIES_DB = os.path.join(ANTIGRAVITY_DIR, 'conversation_summaries.db')

SYNC_MANIFEST_PATH = os.path.join(ACCOUNTS_DIR, 'sync_manifest.json')
PROFILE_SYNC_MANIFEST_PATH = os.path.join(ACCOUNTS_DIR, 'profile_sync_manifest.json')
TASK_ISOLATION_MANIFEST_PATH = os.path.join(ANTIGRAVITY_DIR, 'task_isolation_manifest.json')
TASKS_DIR = os.path.join(ANTIGRAVITY_DIR, 'tasks')
SCHEDULED_DIR = os.path.join(ANTIGRAVITY_DIR, 'scheduled')

def get_primary_account():
    """Dynamically get primary account without hardcoding credentials."""
    try:
        man_path = os.path.join(ACCOUNTS_DIR, 'manifest.json')
        if os.path.exists(man_path):
            with open(man_path, 'r', encoding='utf-8') as f:
                m = json.load(f)
                if m:
                    return list(m.keys())[0]
    except Exception:
        pass
    try:
        import quota_engine
        q = quota_engine.fetch_quota_and_tier()
        if q and q.get('email'):
            return q['email']
    except Exception:
        pass
    return "primary_account"

def get_secondary_account():
    """Dynamically get secondary account from manifest."""
    try:
        man_path = os.path.join(ACCOUNTS_DIR, 'manifest.json')
        if os.path.exists(man_path):
            with open(man_path, 'r', encoding='utf-8') as f:
                m = json.load(f)
                if len(m) > 1:
                    return list(m.keys())[1]
    except Exception:
        pass
    return "secondary_account"

PRIMARY_ACCOUNT = get_primary_account()
SECONDARY_ACCOUNT = get_secondary_account()

def norm_account(acc):
    """Normalize account aliases (instance_1, instance_2, primary, secondary) to canonical email."""
    if not acc:
        return ""
    a = str(acc).strip().lower()
    p = get_primary_account().lower()
    s = get_secondary_account().lower()
    if a in ('instance_1', 'primary', 'acc1') or (p and a == p):
        return get_primary_account()
    if a in ('instance_2', 'secondary', 'acc2') or (s and a == s):
        return get_secondary_account()
    return str(acc).strip()

def ensure_dirs():
    """Ensure all required directories exist."""
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
    os.makedirs(BRAIN_DIR, exist_ok=True)
    os.makedirs(ACCOUNTS_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(TASKS_DIR, exist_ok=True)
    os.makedirs(SCHEDULED_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PROJECTS_DIR):
        try:
            os.makedirs(CONFIG_PROJECTS_DIR, exist_ok=True)
        except Exception:
            pass

# ==============================================================================
# 1. PROFILE & PROJECT SELECTIVE SYNC MANIFEST
# ==============================================================================

def load_profile_sync_manifest():
    """
    Load the profile synchronization manifest mapping projects, conversations,
    and workspaces to specific Google accounts / instances.
    """
    ensure_dirs()
    if os.path.exists(PROFILE_SYNC_MANIFEST_PATH):
        try:
            with open(PROFILE_SYNC_MANIFEST_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

    # Default initial state: Primary account owns all existing projects,
    # switcher project is shared, others isolated unless explicitly designated.
    initial_manifest = {
        "version": "2.0",
        "updated_at": datetime.datetime.now().isoformat(),
        "accounts": {
            PRIMARY_ACCOUNT: {
                "label": "Primary Account",
                "projects": [],
                "conversations": []
            },
            SECONDARY_ACCOUNT: {
                "label": "Secondary Account",
                "projects": [],
                "conversations": []
            }
        },
        "project_profiles": {},
        "conversation_profiles": {}
    }
    
    # Auto-seed existing projects
    projects = discover_raw_projects()
    for pid, pdata in projects.items():
        assigned = [PRIMARY_ACCOUNT, SECONDARY_ACCOUNT] if SECONDARY_ACCOUNT else [PRIMARY_ACCOUNT]
        initial_manifest["project_profiles"][pid] = {
            "name": pdata.get("name", pid),
            "path": pdata.get("path", ""),
            "assigned_accounts": assigned,
            "sync_mode": "shared"
        }
        initial_manifest["accounts"][PRIMARY_ACCOUNT]["projects"].append(pid)
        if SECONDARY_ACCOUNT:
            initial_manifest["accounts"][SECONDARY_ACCOUNT]["projects"].append(pid)

    save_profile_sync_manifest(initial_manifest)
    return initial_manifest

def save_profile_sync_manifest(manifest):
    """Safely persist the profile synchronization manifest."""
    ensure_dirs()
    manifest["updated_at"] = datetime.datetime.now().isoformat()
    try:
        temp_path = f"{PROFILE_SYNC_MANIFEST_PATH}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        if os.path.exists(PROFILE_SYNC_MANIFEST_PATH):
            os.replace(temp_path, PROFILE_SYNC_MANIFEST_PATH)
        else:
            os.rename(temp_path, PROFILE_SYNC_MANIFEST_PATH)
        return True
    except Exception as e:
        try:
            with open(PROFILE_SYNC_MANIFEST_PATH, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

def discover_raw_projects():
    """Read all project files from .gemini/config/projects/."""
    projects = {}
    if not os.path.exists(CONFIG_PROJECTS_DIR):
        return projects

    for fname in os.listdir(CONFIG_PROJECTS_DIR):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(CONFIG_PROJECTS_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                pdata = json.load(f)
                pid = pdata.get('id', os.path.splitext(fname)[0])
                pname = pdata.get('name', pid)
                puri = ''
                res_list = pdata.get('projectResources', {}).get('resources', [])
                for r in res_list:
                    if 'folderUri' in r:
                        puri = r['folderUri']
                        break
                    if 'gitFolder' in r and 'folderUri' in r['gitFolder']:
                        puri = r['gitFolder']['folderUri']
                        break
                if puri.startswith('file:///'):
                    puri = urllib.parse.unquote(puri[8:]).replace('/', '\\')
                projects[pid] = {'id': pid, 'name': pname, 'path': puri}
        except Exception:
            pass
    return projects

def get_project_conversation_counts():
    """Count active conversations per project ID using conversation_summaries.db."""
    counts = {}
    if os.path.exists(CONVERSATION_SUMMARIES_DB):
        try:
            conn = sqlite3.connect(f"file:{CONVERSATION_SUMMARIES_DB}?mode=ro", uri=True, timeout=30.0)
            cur = conn.cursor()
            cur.execute("SELECT project_id, COUNT(*) FROM conversation_summaries GROUP BY project_id")
            for row in cur.fetchall():
                counts[row[0]] = row[1]
            conn.close()
        except Exception:
            pass
    return counts

def list_projects(account=None):
    """
    List all local projects with their assignment status, paths, conversation counts,
    and dual-instance enablement status.
    """
    manifest = load_profile_sync_manifest()
    raw_projects = discover_raw_projects()
    conv_counts = get_project_conversation_counts()
    project_profiles = manifest.get("project_profiles", {})

    items = []
    # Merge discovered raw projects with manifest
    all_pids = set(raw_projects.keys()).union(set(project_profiles.keys()))

    for pid in all_pids:
        raw = raw_projects.get(pid, {})
        prof = project_profiles.get(pid, {})
        
        name = prof.get("name") or raw.get("name") or pid
        path = prof.get("path") or raw.get("path") or ""
        assigned = prof.get("assigned_accounts", [get_primary_account()])
        quota_account = norm_account(prof.get("quota_account") or (assigned[0] if assigned else get_primary_account()))
        count = conv_counts.get(pid, 0)
        
        item = {
            "id": pid,
            "name": name,
            "path": path,
            "assigned_accounts": assigned,
            "quota_account": quota_account,
            "conversation_count": count,
            "enabled_all": prof.get("enabled_all", False),
            "disabled_all": prof.get("disabled_all", len(assigned) == 0),
            "is_instance1_enabled": any(get_primary_account().lower() in a.lower() for a in assigned),
            "is_instance2_enabled": any(get_secondary_account().lower() in a.lower() for a in assigned),
            "is_shared": (len(assigned) > 1 or prof.get("enabled_all", False)),
            "sync_mode": prof.get("sync_mode", "shared" if len(assigned) > 1 else "isolated")
        }

        if account:
            acc_clean = norm_account(account).lower()
            if not any(norm_account(a).lower() == acc_clean for a in assigned):
                continue

        items.append(item)

    # Sort projects: active first, then by conversation count descending
    items.sort(key=lambda x: (x["disabled_all"], -x["conversation_count"], x["name"].lower()))
    return items

def set_project_assignment(project_id, accounts, sync_mode='shared', enabled=None):
    """
    Assign a project to one or more accounts (e.g. ['account1@example.com', 'account2@example.com']).
    Supports passing a single account string with enabled=True/False to toggle assignment.
    """
    manifest = load_profile_sync_manifest()
    raw_projects = discover_raw_projects()

    if project_id not in manifest.get("project_profiles", {}):
        raw = raw_projects.get(project_id, {})
        manifest.setdefault("project_profiles", {})[project_id] = {
            "name": raw.get("name", project_id),
            "path": raw.get("path", ""),
            "assigned_accounts": [],
            "sync_mode": sync_mode
        }

    existing = list(manifest["project_profiles"][project_id].get("assigned_accounts", []))
    existing = [norm_account(x) for x in existing if x]

    if isinstance(accounts, str):
        target = norm_account(accounts)
        if enabled is False:
            existing = [a for a in existing if norm_account(a).lower() != target.lower()]
        elif enabled is True:
            if not any(norm_account(a).lower() == target.lower() for a in existing):
                existing.append(target)
        else:
            existing = [target]
        clean_accounts = existing
    else:
        clean_accounts = list(dict.fromkeys([norm_account(a) for a in accounts if a and norm_account(a)]))

    manifest["project_profiles"][project_id]["assigned_accounts"] = clean_accounts
    manifest["project_profiles"][project_id]["sync_mode"] = sync_mode if clean_accounts else "disabled"
    manifest["project_profiles"][project_id]["disabled_all"] = (len(clean_accounts) == 0)
    manifest["project_profiles"][project_id]["enabled_all"] = False

    save_profile_sync_manifest(manifest)
    return {
        "success": True,
        "project_id": project_id,
        "assigned_accounts": clean_accounts,
        "sync_mode": manifest["project_profiles"][project_id]["sync_mode"]
    }

def toggle_project_all(project_id, state="all"):
    """Enable or disable a project for all saved accounts."""
    manifest = load_profile_sync_manifest()
    raw_projects = discover_raw_projects()
    prof = manifest.setdefault("project_profiles", {}).setdefault(project_id, {
        "name": raw_projects.get(project_id, {}).get("name", project_id),
        "path": raw_projects.get(project_id, {}).get("path", "")
    })
    
    if state == "all":
        man_path = os.path.join(ACCOUNTS_DIR, 'manifest.json')
        saved_accs = []
        if os.path.exists(man_path):
            try:
                with open(man_path, 'r', encoding='utf-8') as f:
                    saved_accs = list(json.load(f).keys())
            except Exception:
                pass
        if not saved_accs:
            saved_accs = [get_primary_account()]
        prof["assigned_accounts"] = saved_accs
        prof["enabled_all"] = True
        prof["disabled_all"] = False
        prof["sync_mode"] = "shared"
    else:
        prof["assigned_accounts"] = []
        prof["enabled_all"] = False
        prof["disabled_all"] = True
        prof["sync_mode"] = "disabled"

    save_profile_sync_manifest(manifest)
    return {
        "success": True,
        "project_id": project_id,
        "state": state,
        "assigned_accounts": prof["assigned_accounts"]
    }

def get_project_quota_account(project_id):
    """Retrieve the designated quota payer account for a project."""
    manifest = load_profile_sync_manifest()
    prof = manifest.get("project_profiles", {}).get(project_id, {})
    assigned = prof.get("assigned_accounts", [])
    return norm_account(prof.get("quota_account") or (assigned[0] if assigned else get_primary_account()))

def set_project_quota_account(project_id, account):
    """
    Explicitly set which account's quota is consumed for this project.
    Ensures that account is added to assigned_accounts so it has project access.
    """
    manifest = load_profile_sync_manifest()
    raw_projects = discover_raw_projects()
    prof = manifest.setdefault("project_profiles", {}).setdefault(project_id, {
        "name": raw_projects.get(project_id, {}).get("name", project_id),
        "path": raw_projects.get(project_id, {}).get("path", "")
    })
    clean_acc = norm_account(account)
    prof["quota_account"] = clean_acc
    assigned = [norm_account(x) for x in prof.get("assigned_accounts", []) if x]
    if clean_acc and not any(a.lower() == clean_acc.lower() for a in assigned):
        assigned.append(clean_acc)
        prof["assigned_accounts"] = assigned
        prof["disabled_all"] = False

    # Sync quota_account into project local config.json if present
    p_path = prof.get("path")
    if p_path and os.path.isdir(p_path):
        cfg_path = os.path.join(p_path, "config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as cf:
                    cfg_data = json.load(cf)
                cfg_data["quota_account"] = clean_acc
                with open(cfg_path, "w", encoding="utf-8") as cf:
                    json.dump(cfg_data, cf, indent=2, ensure_ascii=False)
            except Exception:
                pass

    save_profile_sync_manifest(manifest)
    return {
        "success": True,
        "project_id": project_id,
        "quota_account": clean_acc,
        "assigned_accounts": prof["assigned_accounts"]
    }

def sync_project_to_account(project_id, target_account, include_conversations=False):
    """
    Selectively link or sync a project to target_account.
    """
    manifest = load_profile_sync_manifest()
    raw_projects = discover_raw_projects()
    prof = manifest.setdefault("project_profiles", {}).setdefault(project_id, {
        "name": raw_projects.get(project_id, {}).get("name", project_id),
        "path": raw_projects.get(project_id, {}).get("path", ""),
        "assigned_accounts": [PRIMARY_ACCOUNT],
        "sync_mode": "isolated"
    })
    
    tgt = norm_account(target_account)
    assigned = [norm_account(a) for a in prof.get("assigned_accounts", []) if a]
    if tgt and tgt not in assigned:
        assigned.append(tgt)
    prof["assigned_accounts"] = assigned
    prof["sync_mode"] = "shared" if len(assigned) > 1 else "isolated"

    # Synchronize account index lists
    for acc in [PRIMARY_ACCOUNT, SECONDARY_ACCOUNT, tgt]:
        if not acc:
            continue
        acc_dict = manifest.setdefault("accounts", {}).setdefault(acc, {"projects": [], "conversations": []})
        proj_list = acc_dict.setdefault("projects", [])
        if any(acc.lower() == a.lower() for a in assigned):
            if project_id not in proj_list:
                proj_list.append(project_id)
        else:
            if project_id in proj_list:
                proj_list.remove(project_id)

    if include_conversations:
        convs = list_conversations(project_id=project_id)
        tgt_convs = manifest.setdefault("accounts", {}).setdefault(tgt, {}).setdefault("conversations", [])
        for c in convs:
            cid = c["id"]
            c_prof = manifest.setdefault("conversation_profiles", {}).setdefault(cid, {"assigned_accounts": [PRIMARY_ACCOUNT]})
            c_assigned = [norm_account(a) for a in c_prof.get("assigned_accounts", []) if a]
            if tgt and tgt not in c_assigned:
                c_assigned.append(tgt)
            c_prof["assigned_accounts"] = c_assigned
            if cid not in tgt_convs:
                tgt_convs.append(cid)

    save_profile_sync_manifest(manifest)
    return {"success": True, "project_id": project_id, "target_account": tgt, "assigned_accounts": assigned}

def unlink_project_from_account(project_id, account):
    """
    Remove an account from a project's assigned profiles so it does NOT appear
    or bleed into that account's instance window.
    """
    manifest = load_profile_sync_manifest()
    prof = manifest.setdefault("project_profiles", {}).get(project_id)
    if not prof:
        return {"success": False, "error": f"Project '{project_id}' not found"}

    target_acc = norm_account(account)
    assigned = [norm_account(a) for a in prof.get("assigned_accounts", []) if a]
    updated = [a for a in assigned if a.lower() != target_acc.lower()]
    
    # Never leave primary account completely unassigned if it's the only one
    if not updated and target_acc.lower() != PRIMARY_ACCOUNT.lower():
        updated = [PRIMARY_ACCOUNT]

    prof["assigned_accounts"] = updated
    prof["sync_mode"] = "shared" if len(updated) > 1 else "isolated"

    # Synchronize account index lists
    for acc in [PRIMARY_ACCOUNT, SECONDARY_ACCOUNT, target_acc]:
        if not acc:
            continue
        acc_dict = manifest.setdefault("accounts", {}).setdefault(acc, {"projects": [], "conversations": []})
        proj_list = acc_dict.setdefault("projects", [])
        if any(acc.lower() == a.lower() for a in updated):
            if project_id not in proj_list:
                proj_list.append(project_id)
        else:
            if project_id in proj_list:
                proj_list.remove(project_id)

    # Also unlink conversations of this project from target_account
    conv_profiles = manifest.setdefault("conversation_profiles", {})
    convs = list_conversations(project_id=project_id)
    target_convs = manifest.setdefault("accounts", {}).setdefault(target_acc, {}).setdefault("conversations", [])
    for c in convs:
        cid = c["id"]
        if cid in conv_profiles:
            c_assigned = [norm_account(a) for a in conv_profiles[cid].get("assigned_accounts", []) if a]
            c_updated = [a for a in c_assigned if a.lower() != target_acc.lower()]
            if not c_updated:
                c_updated = [PRIMARY_ACCOUNT]
            conv_profiles[cid]["assigned_accounts"] = c_updated
        if cid in target_convs:
            target_convs.remove(cid)

    save_profile_sync_manifest(manifest)
    return {"success": True, "project_id": project_id, "unlinked_account": target_acc, "remaining_accounts": updated}

# ==============================================================================
# 2. CONVERSATIONS & TIMELINES MANAGEMENT
# ==============================================================================

def get_conversation_title(conv_id):
    """Extract human-readable title or first prompt for a conversation."""
    transcript_path = os.path.join(BRAIN_DIR, conv_id, '.system_generated', 'logs', 'transcript.jsonl')
    if os.path.exists(transcript_path):
        try:
            with open(transcript_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if data.get('type') == 'USER_INPUT' or data.get('source') == 'USER_EXPLICIT':
                            content = data.get('content', '').strip()
                            if content:
                                clean = content.replace('<USER_REQUEST>', '').replace('</USER_REQUEST>', '').strip()
                                first_line = clean.split('\n')[0].strip()
                                return (first_line[:75] + '...') if len(first_line) > 75 else first_line
                    except Exception:
                        continue
        except Exception:
            pass
    return f"Conversation {conv_id[:8]}"

def get_conversation_summaries_metadata():
    """Extract preview, title, and project_id from conversation_summaries.db."""
    meta = {}
    if os.path.exists(CONVERSATION_SUMMARIES_DB):
        try:
            conn = sqlite3.connect(f"file:{CONVERSATION_SUMMARIES_DB}?mode=ro", uri=True, timeout=30.0)
            cur = conn.cursor()
            cur.execute("SELECT conversation_id, title, preview, project_id, workspace_uris, app_data_dir FROM conversation_summaries")
            for row in cur.fetchall():
                cid, title, preview, pid, w_uris, app_data = row
                meta[cid] = {
                    "title": title or preview or "",
                    "preview": preview or "",
                    "project_id": pid or "outside-of-project",
                    "workspace_uris": w_uris or "",
                    "app_data_dir": app_data or "antigravity"
                }
            conn.close()
        except Exception:
            pass
    return meta

def list_conversations(account=None, project_id=None):
    """
    List all local conversations with metadata (title, project, assigned accounts,
    last modified, size, artifacts).
    """
    ensure_dirs()
    manifest = load_profile_sync_manifest()
    project_profiles = manifest.get("project_profiles", {})
    conv_profiles = manifest.get("conversation_profiles", {})
    db_meta = get_conversation_summaries_metadata()

    db_files = glob.glob(os.path.join(CONVERSATIONS_DIR, '*.db'))
    conversations = []

    for db_path in db_files:
        basename = os.path.basename(db_path)
        conv_id = os.path.splitext(basename)[0]
        
        # Skip WAL/SHM temporary files
        if '-wal' in conv_id or '-shm' in conv_id:
            continue

        try:
            stat = os.stat(db_path)
            mtime = stat.st_mtime
            size_kb = round(stat.st_size / 1024, 1)
            
            brain_folder = os.path.join(BRAIN_DIR, conv_id)
            has_brain = os.path.isdir(brain_folder)
            
            c_meta = db_meta.get(conv_id, {})
            c_pid = c_meta.get("project_id") or "outside-of-project"
            
            # Resolve project title
            p_prof = project_profiles.get(c_pid, {})
            p_name = p_prof.get("name") or c_pid
            
            # Determine assigned accounts:
            # 1. Explicit conversation assignment in manifest
            # 2. Inherited from project assignment
            # 3. Default to Primary Account
            if conv_id in conv_profiles and conv_profiles[conv_id].get("assigned_accounts"):
                assigned_accounts = conv_profiles[conv_id]["assigned_accounts"]
            elif c_pid in project_profiles and project_profiles[c_pid].get("assigned_accounts"):
                assigned_accounts = project_profiles[c_pid]["assigned_accounts"]
            else:
                assigned_accounts = [PRIMARY_ACCOUNT]

            if project_id and c_pid != project_id:
                continue

            if account:
                acc_clean = norm_account(account)
                if not any(acc_clean.lower() == norm_account(a).lower() for a in assigned_accounts):
                    continue

            title = c_meta.get("title") or get_conversation_title(conv_id)
            dt_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')

            conversations.append({
                'id': conv_id,
                'title': title,
                'project_id': c_pid,
                'project_name': p_name,
                'assigned_accounts': assigned_accounts,
                'is_in_instance2': any(SECONDARY_ACCOUNT.lower() in a.lower() for a in assigned_accounts),
                'last_modified': dt_str,
                'timestamp': mtime,
                'size_kb': size_kb,
                'has_brain': has_brain
            })
        except Exception:
            continue

    # Sort descending by last modified
    conversations.sort(key=lambda x: x['timestamp'], reverse=True)
    return conversations

def get_allowed_conversations(account):
    """
    Returns list of conversation IDs allowed for the given account/instance.
    Used for selective DOM filtering in Antigravity.
    """
    target = norm_account(account)
    convs = list_conversations(account=target)
    allowed = [c["id"] for c in convs]
    if not allowed:
        all_convs = list_conversations()
        return [c["id"] for c in all_convs]
    return allowed

def assign_conversation_account(conv_id, account, action='add'):
    """Add or remove an account from a conversation's active assignment."""
    manifest = load_profile_sync_manifest()
    c_prof = manifest.setdefault("conversation_profiles", {}).setdefault(conv_id, {"assigned_accounts": []})
    assigned = [norm_account(a) for a in c_prof.get("assigned_accounts", []) if a]

    acc_target = norm_account(account)
    if action == 'add':
        if acc_target and acc_target not in assigned:
            assigned.append(acc_target)
    elif action == 'remove':
        assigned = [a for a in assigned if a.lower() != acc_target.lower()]
        if not assigned:
            assigned = [PRIMARY_ACCOUNT]

    c_prof["assigned_accounts"] = assigned

    # Synchronize account conversation index lists
    for acc in [PRIMARY_ACCOUNT, SECONDARY_ACCOUNT, acc_target]:
        if not acc:
            continue
        acc_dict = manifest.setdefault("accounts", {}).setdefault(acc, {"projects": [], "conversations": []})
        c_list = acc_dict.setdefault("conversations", [])
        if any(acc.lower() == a.lower() for a in assigned):
            if conv_id not in c_list:
                c_list.append(conv_id)
        else:
            if conv_id in c_list:
                c_list.remove(conv_id)

    if not save_profile_sync_manifest(manifest):
        return {"success": False, "error": "Conversation profile could not be saved", "conversation_id": conv_id}
    return {"success": True, "conversation_id": conv_id, "assigned_accounts": assigned}

# ==============================================================================
# 3. SCHEDULED TASKS ISOLATION ENGINE
# ==============================================================================

def load_task_manifest():
    """
    Load task isolation manifest controlling which account and instance
    can run or trigger scheduled tasks / crons.
    """
    ensure_dirs()
    if os.path.exists(TASK_ISOLATION_MANIFEST_PATH):
        try:
            with open(TASK_ISOLATION_MANIFEST_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

    # Default isolation rules for identified Windows tasks
    default_manifest = {
        "version": "2.0",
        "updated_at": datetime.datetime.now().isoformat(),
        "tasks": {
            "SamansaDailySEOAgent": {
                "name": "SamansaDailySEOAgent",
                "owner_account": PRIMARY_ACCOUNT,
                "allowed_instances": ["instance_1"],
                "isolated_from_account2": True,
                "enabled": True,
                "system_type": "windows_scheduled_task",
                "project_path": os.path.expandvars(r"%USERPROFILE%\Desktop\agent-helper\samansa SEO Agent"),
                "description": "Daily SEO Agent Runner (12:30 PM)"
            },
            "NabiPerfume_Daily_SEO": {
                "name": "NabiPerfume_Daily_SEO",
                "owner_account": PRIMARY_ACCOUNT,
                "allowed_instances": ["instance_1"],
                "isolated_from_account2": True,
                "enabled": True,
                "system_type": "windows_scheduled_task",
                "project_path": os.path.expandvars(r"%USERPROFILE%\Desktop\agent-helper\nabi perfume SEO"),
                "description": "Nabi Perfume SEO Automation"
            },
            "Nabi_Daily_SEO_1230": {
                "name": "Nabi_Daily_SEO_1230",
                "owner_account": PRIMARY_ACCOUNT,
                "allowed_instances": ["instance_1"],
                "isolated_from_account2": True,
                "enabled": True,
                "system_type": "windows_scheduled_task",
                "project_path": os.path.expandvars(r"%USERPROFILE%\Desktop\agent-helper\nabi perfume SEO"),
                "description": "Nabi Daily SEO 12:30 Trigger"
            },
            "AntigravityQuotaMonitor": {
                "name": "AntigravityQuotaMonitor",
                "owner_account": "shared",
                "allowed_instances": ["instance_1", "instance_2"],
                "isolated_from_account2": False,
                "enabled": True,
                "system_type": "windows_scheduled_task",
                "project_path": "",
                "description": "Real-time Multi-Instance Quota Auto-Sync Daemon"
            }
        },
        "account_rules": {
            PRIMARY_ACCOUNT: {
                "allow_running_tasks": True,
                "assigned_tasks": ["SamansaDailySEOAgent", "NabiPerfume_Daily_SEO", "Nabi_Daily_SEO_1230", "AntigravityQuotaMonitor"]
            },
            SECONDARY_ACCOUNT: {
                "allow_running_tasks": True,
                "assigned_tasks": ["AntigravityQuotaMonitor"],
                "blocked_tasks": ["SamansaDailySEOAgent", "NabiPerfume_Daily_SEO", "Nabi_Daily_SEO_1230"]
            }
        }
    }
    save_task_manifest(default_manifest)
    return default_manifest

def save_task_manifest(manifest):
    """Safely persist task isolation manifest."""
    ensure_dirs()
    manifest["updated_at"] = datetime.datetime.now().isoformat()
    try:
        temp_path = f"{TASK_ISOLATION_MANIFEST_PATH}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        if os.path.exists(TASK_ISOLATION_MANIFEST_PATH):
            os.replace(temp_path, TASK_ISOLATION_MANIFEST_PATH)
        else:
            os.rename(temp_path, TASK_ISOLATION_MANIFEST_PATH)
        return True
    except Exception:
        try:
            with open(TASK_ISOLATION_MANIFEST_PATH, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

_tasks_cache = {}
_tasks_cache_time = 0

def discover_windows_scheduled_tasks(force=False):
    """Query live Windows Scheduled Tasks matching agent or developer keywords."""
    global _tasks_cache, _tasks_cache_time
    now = time.time()
    if not force and _tasks_cache and (now - _tasks_cache_time < 60):
        return _tasks_cache

    tasks = {}
    ignore_prefixes = ['microsoft\\', 'asus\\', 'agent activation runtime', 'adobe\\', 'google\\']
    try:
        cmd = ['schtasks', '/query', '/fo', 'csv', '/nh']
        kwargs = {'capture_output': True, 'text': True, 'errors': 'ignore'}
        if platform.system().lower() == 'windows':
            kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            try:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                kwargs['startupinfo'] = si
            except Exception:
                pass
        res = subprocess.run(cmd, **kwargs)
        for line in res.stdout.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip().strip('"') for p in line.split('","')]
            if not parts:
                continue
            tname = parts[0].lstrip('\\')
            tname_lower = tname.lower()
            if any(tname_lower.startswith(pref) for pref in ignore_prefixes):
                continue
            if any(k in tname_lower for k in ['antigravity', 'samansa', 'seo', 'agent', 'nabi', 'quota']):
                next_run = parts[1] if len(parts) > 1 else "N/A"
                status = parts[2] if len(parts) > 2 else "Unknown"
                tasks[tname] = {
                    "name": tname,
                    "next_run": next_run,
                    "status": status,
                    "enabled": (status.lower() != "disabled")
                }
        _tasks_cache = tasks
        _tasks_cache_time = now
    except Exception:
        pass
    return tasks

def list_scheduled_tasks(account=None):
    """
    List all developer / agent scheduled tasks with isolation states, assigned accounts, and owner accounts.
    """
    manifest = load_task_manifest()
    known_tasks = manifest.get("tasks", {})
    live_tasks = discover_windows_scheduled_tasks()

    all_names = set(known_tasks.keys()).union(set(live_tasks.keys()))
    task_list = []

    for name in all_names:
        m_info = known_tasks.get(name, {})
        l_info = live_tasks.get(name, {})

        owner = m_info.get("owner_account", PRIMARY_ACCOUNT)
        
        # Dynamic multi-account assignment support
        assigned = m_info.get("assigned_accounts")
        if assigned is None:
            is_isolated = m_info.get("isolated_from_account2", (owner.lower() == PRIMARY_ACCOUNT.lower()))
            if is_isolated:
                assigned = [owner]
            else:
                assigned = [PRIMARY_ACCOUNT, SECONDARY_ACCOUNT] if SECONDARY_ACCOUNT else [PRIMARY_ACCOUNT]
        clean_assigned = [norm_account(a) for a in assigned if a]

        disabled_all = m_info.get("disabled_all", len(clean_assigned) == 0)
        enabled_all = m_info.get("enabled_all", False)
        
        status = l_info.get("status") or ("Ready" if m_info.get("enabled", True) and not disabled_all else "Disabled")
        enabled = (status.lower() != "disabled") and m_info.get("enabled", True) and not disabled_all
        next_run = l_info.get("next_run", "Scheduled")
        desc = m_info.get("description") or f"Scheduled Agent Task: {name}"

        # If user wants to filter by account
        if account:
            acc_clean = norm_account(account)
            if acc_clean and not any(a.lower() == acc_clean.lower() for a in clean_assigned):
                status = f"Isolated (Blocked in {acc_clean})"
                enabled = False

        quota_account = norm_account(m_info.get("quota_account") or owner)

        task_list.append({
            "name": name,
            "task_name": name,
            "owner_account": owner,
            "quota_account": quota_account,
            "assigned_accounts": clean_assigned,
            "disabled_all": disabled_all,
            "enabled_all": enabled_all,
            "status": status,
            "enabled": enabled,
            "isolated_from_account2": (SECONDARY_ACCOUNT not in clean_assigned),
            "allowed_instances": m_info.get("allowed_instances", ["instance_1", "instance_2"]),
            "next_run": next_run,
            "description": desc,
            "project_path": m_info.get("project_path", "")
        })

    task_list.sort(key=lambda x: (x["owner_account"] == "shared", x["name"]))
    return task_list

def set_task_account_assignment(task_name, accounts, enabled=None):
    """
    Assign arbitrary accounts to a scheduled task or toggle an account on/off.
    accounts can be a list of account emails, or a single account string with enabled (True/False).
    """
    manifest = load_task_manifest()
    tasks = manifest.setdefault("tasks", {})
    task_entry = tasks.setdefault(task_name, {
        "name": task_name,
        "system_type": "windows_scheduled_task"
    })

    existing = task_entry.get("assigned_accounts")
    if existing is None:
        owner = norm_account(task_entry.get("owner_account", PRIMARY_ACCOUNT))
        is_iso = task_entry.get("isolated_from_account2", True)
        existing = [owner] if is_iso else ([PRIMARY_ACCOUNT, SECONDARY_ACCOUNT] if SECONDARY_ACCOUNT else [PRIMARY_ACCOUNT])
    existing = [norm_account(a) for a in existing if a]

    if isinstance(accounts, str):
        target = norm_account(accounts)
        if enabled is False:
            existing = [a for a in existing if norm_account(a).lower() != target.lower()]
        elif enabled is True:
            if not any(norm_account(a).lower() == target.lower() for a in existing):
                existing.append(target)
        else:
            existing = [target]
        clean_accounts = existing
    else:
        clean_accounts = list(dict.fromkeys([norm_account(a) for a in accounts if a and norm_account(a)]))

    disabled_all = (len(clean_accounts) == 0)
    task_entry["assigned_accounts"] = clean_accounts
    task_entry["disabled_all"] = disabled_all
    task_entry["enabled_all"] = False
    task_entry["enabled"] = not disabled_all
    task_entry["isolated_from_account2"] = (norm_account(SECONDARY_ACCOUNT).lower() not in [a.lower() for a in clean_accounts])
    
    # Sync system schtasks status if on Windows
    if disabled_all:
        try:
            cmd = ['schtasks', '/change', '/tn', task_name, '/disable']
            kwargs = {'capture_output': True, 'text': True}
            if platform.system().lower() == 'windows':
                kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            subprocess.run(cmd, **kwargs)
        except Exception:
            pass
    elif len(clean_accounts) > 0:
        try:
            cmd = ['schtasks', '/change', '/tn', task_name, '/enable']
            kwargs = {'capture_output': True, 'text': True}
            if platform.system().lower() == 'windows':
                kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            subprocess.run(cmd, **kwargs)
        except Exception:
            pass

    save_task_manifest(manifest)
    return {
        "success": True,
        "task_name": task_name,
        "assigned_accounts": clean_accounts,
        "disabled_all": disabled_all,
        "enabled": not disabled_all
    }

def toggle_task_all(task_name, state="all"):
    """Enable or disable a scheduled task for all saved accounts."""
    manifest = load_task_manifest()
    tasks = manifest.setdefault("tasks", {})
    task_entry = tasks.setdefault(task_name, {
        "name": task_name,
        "system_type": "windows_scheduled_task"
    })

    if state == "all":
        man_path = os.path.join(ACCOUNTS_DIR, 'manifest.json')
        saved_accs = []
        if os.path.exists(man_path):
            try:
                with open(man_path, 'r', encoding='utf-8') as f:
                    saved_accs = list(json.load(f).keys())
            except Exception:
                pass
        if not saved_accs:
            saved_accs = [PRIMARY_ACCOUNT]
            if SECONDARY_ACCOUNT:
                saved_accs.append(SECONDARY_ACCOUNT)
        
        task_entry["assigned_accounts"] = saved_accs
        task_entry["enabled_all"] = True
        task_entry["disabled_all"] = False
        task_entry["enabled"] = True
        task_entry["isolated_from_account2"] = False
        
        try:
            cmd = ['schtasks', '/change', '/tn', task_name, '/enable']
            kwargs = {'capture_output': True, 'text': True}
            if platform.system().lower() == 'windows':
                kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            subprocess.run(cmd, **kwargs)
        except Exception:
            pass
    else:
        task_entry["assigned_accounts"] = []
        task_entry["enabled_all"] = False
        task_entry["disabled_all"] = True
        task_entry["enabled"] = False
        task_entry["isolated_from_account2"] = True

        try:
            cmd = ['schtasks', '/change', '/tn', task_name, '/disable']
            kwargs = {'capture_output': True, 'text': True}
            if platform.system().lower() == 'windows':
                kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            subprocess.run(cmd, **kwargs)
        except Exception:
            pass

    save_task_manifest(manifest)
    return {
        "success": True,
        "task_name": task_name,
        "state": state,
        "assigned_accounts": task_entry["assigned_accounts"],
        "enabled": task_entry["enabled"]
    }

def get_task_quota_account(task_name):
    """Retrieve the designated quota payer account for a scheduled task."""
    manifest = load_task_manifest()
    task_entry = manifest.get("tasks", {}).get(task_name, {})
    return norm_account(task_entry.get("quota_account") or task_entry.get("owner_account") or PRIMARY_ACCOUNT)

def set_task_quota_account(task_name, account):
    """
    Explicitly set which account's quota is consumed when this scheduled task executes.
    Ensures that account is in assigned_accounts so it can run the task.
    """
    manifest = load_task_manifest()
    tasks = manifest.setdefault("tasks", {})
    task_entry = tasks.setdefault(task_name, {
        "name": task_name,
        "system_type": "windows_scheduled_task"
    })
    clean_acc = norm_account(account)
    task_entry["quota_account"] = clean_acc
    assigned = [norm_account(x) for x in task_entry.get("assigned_accounts", []) if x]
    if clean_acc and not any(a.lower() == clean_acc.lower() for a in assigned):
        assigned.append(clean_acc)
        task_entry["assigned_accounts"] = assigned
        task_entry["disabled_all"] = False

    # Sync quota_account into task project_path config.json if present
    p_path = task_entry.get("project_path")
    if p_path and os.path.isdir(p_path):
        cfg_path = os.path.join(p_path, "config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as cf:
                    cfg_data = json.load(cf)
                cfg_data["quota_account"] = clean_acc
                with open(cfg_path, "w", encoding="utf-8") as cf:
                    json.dump(cfg_data, cf, indent=2, ensure_ascii=False)
            except Exception:
                pass

    save_task_manifest(manifest)
    return {
        "success": True,
        "task_name": task_name,
        "quota_account": clean_acc,
        "assigned_accounts": task_entry["assigned_accounts"]
    }

def set_task_isolation(task_name, owner_account=PRIMARY_ACCOUNT, isolate_from_account2=True, allowed_instances=None, requesting_account=None):
    """
    Update a task's isolation parameters.
    When isolate_from_account2 is True, Account 2 (Instance 2) is strictly prohibited
    from triggering, enabling, or running this task.
    """
    manifest = load_task_manifest()
    tasks = manifest.setdefault("tasks", {})
    task_entry = tasks.setdefault(task_name, {
        "name": task_name,
        "system_type": "windows_scheduled_task"
    })

    owner_clean = norm_account(task_entry.get("owner_account") or owner_account) or PRIMARY_ACCOUNT

    # Permission check: Block Secondary Account from altering isolation of Primary tasks
    if not requesting_account:
        if os.environ.get("ANTIGRAVITY_INSTANCE_ID") == "instance_2" or os.environ.get("ANTIGRAVITY_ACCOUNT") == SECONDARY_ACCOUNT:
            requesting_account = SECONDARY_ACCOUNT

    if requesting_account:
        req_clean = norm_account(requesting_account)
        if req_clean == SECONDARY_ACCOUNT and owner_clean != SECONDARY_ACCOUNT:
            return {
                "success": False,
                "error": f"مجوز رد شد: تغییر وضعیت ایزولاسیون تسک '{task_name}' متعلق به {owner_clean} از اکانت دوم مجاز نیست."
            }
    task_entry["owner_account"] = owner_clean
    task_entry["isolated_from_account2"] = bool(isolate_from_account2)
    if allowed_instances is not None:
        task_entry["allowed_instances"] = allowed_instances
    else:
        task_entry["allowed_instances"] = ["instance_1"] if isolate_from_account2 else ["instance_1", "instance_2"]

    # Update account_rules
    sec_rules = manifest.setdefault("account_rules", {}).setdefault(SECONDARY_ACCOUNT, {})
    blocked = sec_rules.setdefault("blocked_tasks", [])
    if isolate_from_account2:
        if task_name not in blocked:
            blocked.append(task_name)
    else:
        if task_name in blocked:
            blocked.remove(task_name)

    save_task_manifest(manifest)
    return {
        "success": True,
        "task": task_name,
        "owner_account": owner_clean,
        "isolated_from_account2": isolate_from_account2,
        "allowed_instances": task_entry["allowed_instances"]
    }

def toggle_task_state(task_name, enable=True, requesting_account=None):
    """
    Safely enable or disable a scheduled task with isolation safeguards.
    If requesting_account is secondary account / instance_2 and the task is owned by primary account,
    it strictly denies the operation to prevent cross-account contamination.
    """
    manifest = load_task_manifest()
    task_entry = manifest.get("tasks", {}).get(task_name, {})
    owner = norm_account(task_entry.get("owner_account", PRIMARY_ACCOUNT))
    is_isolated = task_entry.get("isolated_from_account2", True)

    # Permission check: Block Secondary Account from modifying isolated Primary tasks
    if not requesting_account:
        if os.environ.get("ANTIGRAVITY_INSTANCE_ID") == "instance_2" or os.environ.get("ANTIGRAVITY_ACCOUNT") == SECONDARY_ACCOUNT:
            requesting_account = SECONDARY_ACCOUNT

    if requesting_account:
        req_clean = norm_account(requesting_account)
        if req_clean == SECONDARY_ACCOUNT and is_isolated and owner != SECONDARY_ACCOUNT:
            return {
                "success": False,
                "error": f"مجوز رد شد: تسک '{task_name}' متعلق به اکانت {owner} است و در اکانت دوم ایزوله شده است. امکان فعال‌سازی یا تغییر وضعیت آن از اکانت دوم وجود ندارد."
            }

    # Execute system schtasks change if on Windows
    action_flag = '/enable' if enable else '/disable'
    try:
        cmd = ['schtasks', '/change', '/tn', task_name, action_flag]
        kwargs = {'capture_output': True, 'text': True}
        if platform.system().lower() == 'windows':
            kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            try:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                kwargs['startupinfo'] = si
            except Exception:
                pass
        res = subprocess.run(cmd, **kwargs)
        if res.returncode != 0 and 'ERROR' in res.stderr:
            pass
    except Exception:
        pass

    # Update manifest
    manifest.setdefault("tasks", {}).setdefault(task_name, {})["enabled"] = bool(enable)
    save_task_manifest(manifest)

    state_str = "فعال" if enable else "غیرفعال"
    return {
        "success": True,
        "task": task_name,
        "enabled": enable,
        "msg": f"تسک '{task_name}' با موفقیت {state_str} شد."
    }

def check_task_guard(task_name, current_account=None, instance_id=None):
    """
    Runtime execution guard for scheduled tasks, cron jobs, and background runners.
    Returns whether current_account and instance_id are permitted to run task_name.
    Strict multi-account assignment checking.
    """
    manifest = load_task_manifest()
    task_entry = manifest.get("tasks", {}).get(task_name)
    if not task_entry:
        return {"allowed": True, "reason": "Unmanaged task"}

    if task_entry.get("disabled_all") is True or task_entry.get("enabled") is False:
        return {
            "allowed": False,
            "reason": f"Task '{task_name}' is explicitly disabled for all accounts."
        }

    curr_instance = instance_id or os.environ.get("ANTIGRAVITY_INSTANCE_ID", "instance_1")

    if not current_account:
        try:
            import sync_daemon
            current_account = sync_daemon.get_instance_active_account(curr_instance)
        except Exception:
            pass
        if not current_account:
            # Check active_<instance_id>.txt
            f_inst = os.path.join(ACCOUNTS_DIR, f"active_{curr_instance}.txt")
            if os.path.exists(f_inst):
                try:
                    with open(f_inst, "r", encoding="utf-8") as f:
                        current_account = f.read().strip()
                except Exception:
                    pass
        if not current_account:
            active_quota_file = os.path.join(ANTIGRAVITY_DIR, 'active_quota.json')
            if os.path.exists(active_quota_file):
                try:
                    with open(active_quota_file, 'r', encoding='utf-8') as f:
                        q = json.load(f)
                        current_account = q.get('email')
                except Exception:
                    pass
        if not current_account:
            current_account = PRIMARY_ACCOUNT

    curr_clean = norm_account(current_account)
    quota_acc = norm_account(task_entry.get("quota_account") or task_entry.get("owner_account") or PRIMARY_ACCOUNT)

    # Multi-account assignment check
    assigned = task_entry.get("assigned_accounts")
    if assigned is not None:
        clean_assigned = [norm_account(a).lower() for a in assigned if a]
        if curr_clean.lower() not in clean_assigned:
            return {
                "allowed": False,
                "quota_account": quota_acc,
                "reason": f"Task '{task_name}' is assigned only to {assigned}, blocked for '{curr_clean}'."
            }
        return {"allowed": True, "assigned_accounts": assigned, "quota_account": quota_acc}

    # Backward compatibility fallback:
    owner = norm_account(task_entry.get("owner_account", PRIMARY_ACCOUNT))
    allowed_instances = task_entry.get("allowed_instances", ["instance_1"])
    isolated2 = task_entry.get("isolated_from_account2", False)

    if allowed_instances and curr_instance not in allowed_instances:
        return {
            "allowed": False,
            "owner": owner,
            "quota_account": quota_acc,
            "reason": f"Task '{task_name}' is restricted to {allowed_instances}, current instance is '{curr_instance}'."
        }

    if curr_clean == SECONDARY_ACCOUNT and (isolated2 or owner != SECONDARY_ACCOUNT):
        return {
            "allowed": False,
            "owner": owner,
            "quota_account": quota_acc,
            "reason": f"Task '{task_name}' is assigned to '{owner}' and blocked for account 2 ('{curr_clean}')."
        }

    if curr_clean == PRIMARY_ACCOUNT and owner == SECONDARY_ACCOUNT:
        return {
            "allowed": False,
            "owner": owner,
            "quota_account": quota_acc,
            "reason": f"Task '{task_name}' is assigned to '{owner}' and blocked for account 1 ('{curr_clean}')."
        }

    return {"allowed": True, "owner": owner, "quota_account": quota_acc}

def get_account_environment(account_email):
    """
    Returns an environment dictionary configured for a specific account,
    including its fresh OAuth token, API keys, and account identifiers.
    """
    env = os.environ.copy()
    clean_acc = norm_account(account_email)
    env["ANTIGRAVITY_ACCOUNT"] = clean_acc
    env["ANTIGRAVITY_QUOTA_ACCOUNT"] = clean_acc
    
    tok_file = os.path.join(ACCOUNTS_DIR, f"{clean_acc}.token")
    if os.path.exists(tok_file):
        try:
            with open(tok_file, 'r', encoding='utf-8') as f:
                raw_tok = f.read().strip()
            import quota_engine
            fresh_tok = quota_engine.ensure_fresh_token(raw_tok, account_email=clean_acc)
            if fresh_tok:
                access_tok = fresh_tok
                if "access_token" in fresh_tok:
                    try:
                        d = json.loads(fresh_tok)
                        access_tok = d.get("token", {}).get("access_token") or d.get("access_token") or fresh_tok
                    except Exception:
                        pass
                env["GEMINI_CLI_OAUTH_TOKEN"] = access_tok
                env["GOOGLE_OAUTH_ACCESS_TOKEN"] = access_tok
        except Exception:
            pass
    return env

def run_guarded_task(task_name, custom_command=None):
    """
    Executes a task under its designated quota_account credentials,
    enforcing guard rules and capturing execution status.
    """
    manifest = load_task_manifest()
    task_entry = manifest.get("tasks", {}).get(task_name, {})
    quota_acc = norm_account(task_entry.get("quota_account") or task_entry.get("owner_account") or PRIMARY_ACCOUNT)
    
    guard = check_task_guard(task_name, current_account=quota_acc)
    if not guard.get("allowed"):
        return {"success": False, "error": f"Task guard blocked execution: {guard.get('reason')}", "quota_account": quota_acc}

    env = get_account_environment(quota_acc)
    cmd = custom_command
    if not cmd:
        proj_path = task_entry.get("project_path", "")
        if "Samansa" in task_name and proj_path:
            cmd = [sys.executable, os.path.join(proj_path, "daily_seo_runner.py"), "--batch-size", "30"]
        elif "Nabi" in task_name and proj_path:
            bat_path = os.path.join(proj_path, "run_daily_seo.bat")
            if os.path.exists(bat_path):
                cmd = ["cmd.exe", "/c", bat_path]
            else:
                cmd = [sys.executable, os.path.join(proj_path, "daily_seo_runner.py"), "--all"]
        else:
            return {"success": False, "error": f"No execution command configured for task '{task_name}'", "quota_account": quota_acc}

    try:
        kwargs = {"env": env}
        if platform.system().lower() == "windows":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        proc = subprocess.Popen(cmd, **kwargs)
        return {
            "success": True,
            "task_name": task_name,
            "pid": proc.pid,
            "quota_account": quota_acc,
            "msg": f"تسک '{task_name}' با سهمیه اکانت '{quota_acc}' اجرا شد (PID: {proc.pid})"
        }
    except Exception as e:
        return {"success": False, "error": str(e), "quota_account": quota_acc}

# ==============================================================================
# 4. SAFETY BACKUP & CONVERSATION CLONING / MERGING
# ==============================================================================

def _migration_sql_name(name):
    return '"' + name.replace('"', '""') + '"'


def _migration_path(cid):
    # An identifier must never turn a migration into a path outside its store.
    if not isinstance(cid, str) or str(uuid.UUID(cid)) != cid.lower():
        raise ValueError('Invalid conversation identifier')
    return os.path.join(CONVERSATIONS_DIR, cid + '.db')


def _migration_open_readonly(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=5.0)


def _migration_snapshot(source, destination):
    # SQLite's backup API reads committed WAL frames in one consistent snapshot.
    # Reserve the path before opening SQLite: existing conversations must survive.
    if any(os.path.lexists(destination + suffix) for suffix in ('','-wal','-shm')):
        raise FileExistsError('Destination database or recovery sidecar already exists')
    with open(destination, 'xb'):
        pass
    src = dst = None
    try:
        src = _migration_open_readonly(source)
        dst = sqlite3.connect(destination, timeout=5.0)
        deadline = time.monotonic() + 30.0
        def progress(status, remaining, total):
            if time.monotonic() > deadline:
                raise TimeoutError('SQLite backup did not finish within 30 seconds')
        src.backup(dst, pages=256, progress=progress, sleep=0.02)
        dst.execute('PRAGMA journal_mode=DELETE')
        if dst.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('SQLite backup failed integrity check')
    finally:
        if dst is not None:
            dst.close()
        if src is not None:
            src.close()


def _migration_tables(conn):
    return {row[0]: tuple(r[1] for r in conn.execute('PRAGMA table_info(' + _migration_sql_name(row[0]) + ')'))
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def _migration_inspect(conn, allow_embedded=False):
    tables = _migration_tables(conn)
    required = {'trajectory_meta': {'trajectory_id', 'cascade_id'}, 'steps': {'idx', 'step_type', 'status', 'step_payload', 'step_format'}}
    for name, columns in required.items():
        if not columns.issubset(tables.get(name, ())):
            raise ValueError('Unsupported conversation schema: ' + name)
    meta = conn.execute('SELECT trajectory_id,cascade_id FROM trajectory_meta').fetchall()
    if len(meta) != 1 or not all(isinstance(v, str) and v for v in meta[0]):
        raise ValueError('Conversation must contain exactly one identified trajectory')
    counts = {name: conn.execute('SELECT COUNT(*) FROM ' + _migration_sql_name(name)).fetchone()[0] for name in tables}
    if not allow_embedded and 'has_subtrajectory' in tables['steps'] and conn.execute('SELECT 1 FROM steps WHERE has_subtrajectory != 0 LIMIT 1').fetchone():
        raise ValueError('Embedded subtrajectory graphs require a graph-aware native import')
    validation_schema = _migration_get_validation_schema()
    for (idx, fmt, payload) in conn.execute('SELECT idx,step_format,step_payload FROM steps'):
        if not isinstance(idx, int) or idx < 0 or fmt != 0 or not isinstance(payload, bytes):
            raise ValueError('Unsupported step index or payload format')
        _migration_validate_wire(payload,'gemini_coder.Step',validation_schema,allow_embedded=allow_embedded)
        fields = _migration_parse_wire(payload)
        values = {n:v for n,w,v in fields if n in (1,4) and w == 0}
        step_type,status = conn.execute('SELECT step_type,status FROM steps WHERE idx=?',(idx,)).fetchone()
        if values.get(1,0) != step_type or values.get(4,0) != status:
            raise ValueError('Step payload disagrees with its SQL envelope')
    known = {'trajectory_meta','steps','gen_metadata','executor_metadata','parent_references','trajectory_metadata_blob','battle_mode_infos'}
    for table,count in counts.items():
        if table not in known and count:
            raise ValueError('Unsupported populated conversation table: ' + table)
        if table in ('gen_metadata','executor_metadata','parent_references','battle_mode_infos'):
            if not {'idx','data'}.issubset(tables[table]):
                raise ValueError('Unsupported metadata schema: ' + table)
            if any(not isinstance(row[0],int) or row[0] < 0 for row in conn.execute('SELECT idx FROM ' + table)):
                raise ValueError('Unsupported metadata index: ' + table)
    if 'trajectory_metadata_blob' in tables:
        rows = conn.execute('SELECT id FROM trajectory_metadata_blob').fetchall()
        if rows not in ([],[('main',)]):
            raise ValueError('Unsupported trajectory metadata singleton')
    if conn.execute('PRAGMA quick_check').fetchone() != ('ok',):
        raise ValueError('Conversation failed integrity check')
    return {'tables': tables, 'counts': counts, 'trajectory_id': meta[0][0], 'cascade_id': meta[0][1]}


def _migration_signature(conn):
    import hashlib
    digest = hashlib.sha256()
    for name, cols in sorted(_migration_tables(conn).items()):
        digest.update(repr((name, cols)).encode('utf-8'))
        for row in sorted(conn.execute('SELECT * FROM ' + _migration_sql_name(name)).fetchall(), key=repr):
            digest.update(repr(row).encode('utf-8'))
            digest.update(b'\n')
    return digest.hexdigest()


def _migration_read_varint(data, pos):
    value = 0
    shift = 0
    for _ in range(10):
        if pos >= len(data):
            raise ValueError('truncated _migration_varint')
        b = data[pos]
        pos += 1
        value |= (b & 127) << shift
        if b < 128:
            if value >= (1 << 64):
                raise ValueError('oversized protobuf varint')
            return value, pos
        shift += 7
    raise ValueError('oversized _migration_varint')


def _migration_parse_wire(data):
    pos = 0
    fields = []
    while pos < len(data):
        key, pos = _migration_read_varint(data, pos)
        number, wire = key >> 3, key & 7
        if number == 0 or number >= (1 << 29):
            raise ValueError('zero field')
        if wire == 0:
            value, pos = _migration_read_varint(data, pos)
        elif wire in (1, 2, 5):
            if wire == 2:
                size, pos = _migration_read_varint(data, pos)
            else:
                size = 8 if wire == 1 else 4
            if pos + size > len(data):
                raise ValueError('truncated field')
            value = data[pos:pos + size]
            pos += size
        else:
            raise ValueError('unsupported wire type')
        fields.append((number, wire, value))
    return fields


def _migration_varint(n):
    if n < 0:
        n += 1 << 64
    out = bytearray()
    while n > 127:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)
    return bytes(out)


def _migration_encode_wire(fields):
    out = bytearray()
    for n, w, value in fields:
        out += _migration_varint((n << 3) | w)
        if w == 0:
            out += _migration_varint(value)
        elif w == 2:
            out += _migration_varint(len(value)) + value
        elif w in (1, 5):
            out += value
        else:
            raise ValueError('unsupported wire type')
    return bytes(out)




def _migration_get_validation_schema():
    factory = globals().get('_migration_validation_schema')
    if factory is None:
        from migration_proto_schema import _migration_validation_schema as factory
    return factory()


def _migration_validate_wire(data, message, schema=None, depth=0, allow_embedded=True):
    if schema is None:
        schema = _migration_get_validation_schema()
    if not allow_embedded and depth and message == 'gemini_coder.Trajectory':
        raise ValueError('Embedded subtrajectory graphs require a graph-aware native import')
    if depth > 100 or not isinstance(data,bytes):
        raise ValueError('Unsupported protobuf data or nesting')
    rules = schema.get(message)
    if rules is None:
        raise ValueError('Unsupported protobuf message schema: ' + message)
    for n,w,value in _migration_parse_wire(data):
        rule = rules.get(str(n))
        if rule is None:
            continue  # Protobuf unknown fields are deliberately preserved.
        kind,nested,repeated = rule
        expected = 1 if kind in (1,6,16) else 5 if kind in (2,7,15) else 2 if kind in (9,11,12) else 0
        if w != expected:
            if w == 2 and repeated and expected in (0,1,5):
                if expected in (1,5):
                    if len(value) % (8 if expected == 1 else 4):
                        raise ValueError('Truncated packed protobuf field')
                else:
                    pos = 0
                    while pos < len(value):
                        _,pos = _migration_read_varint(value,pos)
                continue
            raise ValueError('Protobuf field has an invalid wire type')
        if kind == 9:
            value.decode('utf-8')
        elif kind == 11:
            _migration_validate_wire(value,nested,schema,depth+1,allow_embedded)


def _migration_wire_schema():
    # Reference-bearing paths reconstructed from the installed public frontend
    # descriptors. User text and unknown fields are preserved; no UUID text search.
    return json.loads(r'''{"exa.cortex_pb.CortexTrajectoryMetadata":{"4":["message","exa.cortex_pb.AgentScriptItem"],"5":["id","parent_conversation_id"],"6":["id","root_conversation_id"],"10":["message","exa.cortex_pb.CustomAgentSpec"],"12":["message","exa.cortex_pb.SourceMetadata"],"22":["message","exa.cortex_pb.BattleModeMetadata"]},"exa.cortex_pb.CortexStepMetadata":{"12":["execution","execution_id"],"20":["message","exa.cortex_pb.SourceTrajectoryStepInfo"]},"exa.cortex_pb.CortexStepGeneratorMetadata":{"1":["message","exa.cortex_pb.ChatModelMetadata"],"2":["step",true],"3":["message","exa.cortex_pb.CascadePlannerConfig"],"4":["execution","execution_id"]},"exa.cortex_pb.ExecutorMetadata":{"3":["step",false],"6":["message","exa.codeium_common_pb.MetricsRecord"],"7":["message","exa.codeium_common_pb.MetricsRecord"],"9":["execution","execution_id"],"10":["message","exa.cortex_pb.CascadeConfig"],"16":["message","exa.cortex_pb.AgentConfigResolution"],"17":["message","exa.cortex_pb.CascadeConfig"]},"exa.cortex_pb.CortexTrajectoryReference":{"1":["id","trajectory_id"],"2":["step",false],"6":["id","conversation_id"]},"exa.cortex_pb.BattleModeInfo":{"1":["id","children_conversation_ids"],"2":["id","winning_conversation_id"],"3":["step",false],"4":["step",false],"8":["id","children_trajectory_ids"],"18":["id","reference_conversation_id"]},"exa.jetski_cortex_pb.CascadeTrajectorySummary":{"4":["id","trajectory_id"],"8":["message","exa.jetski_cortex_pb.CortexTrajectoryStepWithIndex"],"12":["message","exa.jetski_cortex_pb.CortexTrajectoryStepWithIndex"],"14":["message","exa.jetski_cortex_pb.CortexTrajectoryStepWithIndex"],"16":["step",false],"17":["message","exa.cortex_pb.CortexTrajectoryMetadata"],"19":["message","exa.cortex_pb.BattleModeInfo"],"24":["id","fork_parent_conversation_id"]},"exa.cortex_pb.StepRenderInfo":{"9":["message","exa.cortex_pb.StepRenderInfo.TitlePart"],"10":["message","exa.cortex_pb.StepRenderInfo.ContentBlock"]},"gemini_coder.Step":{"5":["message","exa.cortex_pb.CortexStepMetadata"],"6":["message","gemini_coder.Trajectory"],"10":["message","exa.cortex_pb.CortexStepCodeAction"],"19":["message","exa.cortex_pb.CortexStepUserInput"],"30":["message","exa.cortex_pb.CortexStepCheckpoint"],"32":["message","exa.cortex_pb.CortexStepProposeCode"],"47":["message","exa.cortex_pb.CortexStepMcpTool"],"52":["message","exa.cortex_pb.CortexStepTrajectoryChoice"],"71":["message","exa.cortex_pb.CortexStepProposalFeedback"],"95":["message","exa.cortex_pb.CortexStepCodeAcknowledgement"],"114":["message","exa.cortex_pb.CortexStepSystemMessage"],"129":["message","exa.cortex_pb.CortexStepKIInsertion"],"140":["message","exa.cortex_pb.CortexStepGeneric"],"143":["message","exa.cortex_pb.CortexStepInvokeSubagent"],"147":["message","exa.cortex_pb.CompletedInteraction"],"159":["message","gemini_coder.Step"]},"exa.cortex_pb.CustomAgentSpec":{"3":["message","exa.cortex_pb.BuiltinAgentConfig"],"11":["message","exa.cortex_pb.CascadeConfig"],"15":["message","exa.cortex_pb.AgentDiscoveryConfig"],"17":["message","exa.cortex_pb.CustomizationConfig"],"18":["message","exa.cortex_pb.AgentConfig"]},"exa.cortex_pb.SourceMetadata":{"1":["message","exa.cortex_pb.ToolSourceMetadata"]},"exa.cortex_pb.AgentScriptItem":{"7":["message","exa.cortex_pb.CustomAgentSpec"],"11":["message","exa.cortex_pb.CascadeConfig"]},"exa.cortex_pb.BattleModeMetadata":{"2":["id","parent_conversation_id"]},"exa.cortex_pb.SourceTrajectoryStepInfo":{"1":["id","trajectory_id"],"2":["step",false],"3":["gen",false],"4":["id","cascade_id"]},"exa.cortex_pb.ChatModelMetadata":{"2":["message","exa.chat_pb.ChatMessagePrompt"],"9":["message","exa.cortex_pb.ChatStartMetadata"]},"exa.cortex_pb.CascadePlannerConfig":{"2":["message","exa.cortex_pb.CascadeConversationalPlannerConfig"],"26":["message","exa.cortex_pb.CascadeConversationalPlannerConfig"],"36":["message","exa.cortex_pb.CascadeConversationalPlannerConfig"],"42":["message","exa.cortex_pb.CustomizationConfig"],"44":["message","exa.cortex_pb.CascadeConversationalPlannerConfig"],"46":["message","exa.cortex_pb.DeclarativeComponentConfig"],"57":["message","exa.cortex_pb.CustomizationDiscoveryConfig"]},"exa.codeium_common_pb.MetricsRecord":{"7":["id","trajectory_id"]},"exa.cortex_pb.CascadeConfig":{"1":["message","exa.cortex_pb.CascadePlannerConfig"]},"exa.cortex_pb.AgentConfigResolution":{"1":["message","exa.cortex_pb.CustomAgentSpec"]},"exa.jetski_cortex_pb.CortexTrajectoryStepWithIndex":{"1":["message","gemini_coder.Step"],"2":["step",false]},"exa.cortex_pb.StepRenderInfo.TitlePart":{"5":["message","exa.cortex_pb.StepRenderInfo.AgentRef"]},"exa.cortex_pb.StepRenderInfo.ContentBlock":{"4":["message","exa.cortex_pb.StepRenderInfo.AgentRef"],"5":["message","exa.cortex_pb.StepRenderInfo.StepBlock"]},"exa.cortex_pb.CompletedInteraction":{"2":["message","exa.cortex_pb.CascadeUserInteraction"]},"exa.cortex_pb.CortexStepGeneric":{"2":["message","exa.cortex_pb.GenericStepResult"]},"exa.cortex_pb.CortexStepCodeAction":{"1":["message","exa.cortex_pb.ActionSpec"]},"exa.cortex_pb.CortexStepMcpTool":{"9":["message","exa.cortex_pb.StepRenderInfo"]},"exa.cortex_pb.CortexStepCodeAcknowledgement":{"7":["message","exa.cortex_pb.CodeAcknowledgementInfo"]},"exa.cortex_pb.CortexStepSystemMessage":{"2":["message","exa.cortex_pb.StepRenderInfo"],"4":["message","exa.cortex_pb.AgentMessage"]},"exa.cortex_pb.CortexStepKIInsertion":{"1":["message","exa.cortex_pb.CortexStepKIInsertion.KiReferencesEntry"]},"exa.cortex_pb.CortexStepInvokeSubagent":{"5":["id","conversation_id"],"10":["message","exa.cortex_pb.SubagentResult"]},"exa.cortex_pb.CortexStepUserInput":{"12":["message","exa.cortex_pb.CascadeConfig"],"13":["message","exa.cortex_pb.CascadeConfig"],"18":["message","exa.cortex_pb.CustomAgentSpec"]},"exa.cortex_pb.CortexStepCheckpoint":{"3":["step",true],"11":["step",false],"12":["step",false],"18":["message","exa.cortex_pb.TrajectoryFileDiff"],"20":["message","exa.cortex_pb.SubagentSnapshot"],"21":["message","exa.cortex_pb.TaskSnapshot"],"25":["step",false],"26":["message","exa.cortex_pb.AccumulatedSection"]},"exa.cortex_pb.CortexStepProposeCode":{"1":["message","exa.cortex_pb.ActionSpec"]},"exa.cortex_pb.CortexStepTrajectoryChoice":{"1":["id","proposal_trajectory_ids"]},"exa.cortex_pb.CortexStepProposalFeedback":{"2":["step",false]},"gemini_coder.Trajectory":{"1":["id","trajectory_id"],"2":["message","gemini_coder.Step"],"3":["message","exa.cortex_pb.CortexStepGeneratorMetadata"],"5":["message","exa.cortex_pb.CortexTrajectoryReference"],"6":["id","cascade_id"],"7":["message","exa.cortex_pb.CortexTrajectoryMetadata"],"9":["message","exa.cortex_pb.ExecutorMetadata"],"10":["message","exa.cortex_pb.BattleModeInfo"]},"exa.cortex_pb.AgentConfig":{"1":["message","exa.cortex_pb.DeclarativeComponentConfig"],"3":["message","exa.cortex_pb.CascadeConfig"],"4":["message","exa.cortex_pb.CustomizationDiscoveryConfig"]},"exa.cortex_pb.BuiltinAgentConfig":{"3":["message","exa.cortex_pb.CascadeConfig"],"4":["message","exa.cortex_pb.CustomizationDiscoveryConfig"]},"exa.cortex_pb.CustomizationConfig":{"15":["message","exa.cortex_pb.CustomizationDiscoveryConfig"],"18":["id","customization_server_origin_conversation_id"]},"exa.cortex_pb.AgentDiscoveryConfig":{"3":["message","exa.cortex_pb.AgentScriptItem"]},"exa.cortex_pb.ToolSourceMetadata":{"1":["id","conversation_id"],"2":["step",false]},"exa.chat_pb.ChatMessagePrompt":{"18":["step",false],"26":["step",true]},"exa.cortex_pb.ChatStartMetadata":{"1":["step",false]},"exa.cortex_pb.CascadeConversationalPlannerConfig":{"20":["id","override_cascade_id_for_prompt"]},"exa.cortex_pb.DeclarativeComponentConfig":{"1":["message","exa.cortex_pb.FunctionProvider"]},"exa.cortex_pb.CustomizationDiscoveryConfig":{"2":["message","exa.cortex_pb.AgentDiscoveryConfig"]},"exa.cortex_pb.StepRenderInfo.AgentRef":{"1":["id","conversation_id"]},"exa.cortex_pb.StepRenderInfo.StepBlock":{"1":["message","exa.cortex_pb.StepRenderInfo"]},"exa.cortex_pb.CascadeUserInteraction":{"1":["id","trajectory_id"],"2":["step",false]},"exa.cortex_pb.GenericStepResult":{"3":["message","exa.cortex_pb.StepRenderInfo"]},"exa.cortex_pb.ActionSpec":{"3":["step",true]},"exa.cortex_pb.CodeAcknowledgementInfo":{"2":["step",true]},"exa.cortex_pb.AgentMessage":{"12":["message","exa.cortex_pb.SourceMetadata"]},"exa.cortex_pb.CortexStepKIInsertion.KiReferencesEntry":{"2":["message","exa.cortex_pb.KnowledgeReferences"]},"exa.cortex_pb.SubagentResult":{"1":["id","conversation_id"]},"exa.cortex_pb.TrajectoryFileDiff":{"8":["step",false],"9":["step",false]},"exa.cortex_pb.SubagentSnapshot":{"5":["message","exa.cortex_pb.SubagentResult"],"7":["step",false]},"exa.cortex_pb.TaskSnapshot":{"6":["step",false]},"exa.cortex_pb.AccumulatedSection":{"4":["message","exa.cortex_pb.AccumulatedItem"]},"exa.cortex_pb.FunctionProvider":{"4":["id","provider_origin_conversation_id"]},"exa.cortex_pb.KnowledgeReferences":{"1":["message","exa.cortex_pb.KnowledgeReference"]},"exa.cortex_pb.AccumulatedItem":{"3":["message","exa.cortex_pb.AccumulatedItemRenderInfo"]},"exa.cortex_pb.KnowledgeReference":{"2":["id","conversation_id"]},"exa.cortex_pb.AccumulatedItemRenderInfo":{"5":["message","exa.cortex_pb.TrajectoryFileDiff"]}}''')


def _migration_rewrite_wire(data, message, context, depth=0):
    if data is None:
        return None
    if depth > 100 or not isinstance(data, bytes):
        raise ValueError('Invalid or excessive protobuf nesting')
    if depth == 0:
        if '_validation_schema' not in context:
            context['_validation_schema'] = _migration_get_validation_schema()
        _migration_validate_wire(data,message,context['_validation_schema'])
    fields = _migration_parse_wire(data)
    if '_wire_schema' not in context:
        context['_wire_schema'] = _migration_wire_schema()
    rules = context['_wire_schema'].get(message, {})
    # References to another trajectory use that trajectory's offsets, rather
    # than blindly shifting an external parent's index by the current offset.
    local = context
    trajectory_refs = [v.decode('utf-8') for n,w,v in fields if w == 2 and rules.get(str(n)) == ['id','trajectory_id']]
    conversation_refs = [v.decode('utf-8') for n,w,v in fields if w == 2 and rules.get(str(n),[None])[0] == 'id'
                         and rules[str(n)][1] in ('conversation_id','cascade_id')]
    references = trajectory_refs or conversation_refs
    reference_contexts = context['trajectory_contexts' if trajectory_refs else 'conversation_contexts']
    if references:
        matches = [reference_contexts[v] for v in references if v in reference_contexts]
        if matches:
            if any(m['step_offset'] != matches[0]['step_offset'] or m['gen_offset'] != matches[0]['gen_offset'] for m in matches):
                raise ValueError('Inconsistent trajectory reference')
            local = dict(context, **matches[0])
        else:
            local = dict(context, step_offset=0, gen_offset=0)
    # Proto3 scalars without presence omit zero on the wire. Their implicit
    # index zero must move with the source segment, unlike absent optional
    # indices or empty repeated lists. Presence exceptions come from the
    # installed native descriptors (proto3_optional/oneof_index).
    optional_indices = {
        ('exa.jetski_cortex_pb.CascadeTrajectorySummary', 16),
        ('exa.cortex_pb.CortexStepCheckpoint', 25),
        ('exa.cortex_pb.TrajectoryFileDiff', 8),
        ('exa.cortex_pb.TrajectoryFileDiff', 9),
    }
    present = {n for n, _, _ in fields}
    for number, (kind, repeated) in rules.items():
        number = int(number)
        if (kind in ('step', 'gen') and not repeated and number not in present
                and (message, number) not in optional_indices
                and local['step_offset' if kind == 'step' else 'gen_offset']):
            fields.append((number, 0, 0))
    out = []
    for n,w,value in fields:
        rule = rules.get(str(n))
        if rule:
            kind, arg = rule
            if kind == 'message':
                if w != 2:
                    raise ValueError('Invalid protobuf message wire type')
                if not (arg == 'gemini_coder.Trajectory' and context.get('preserve_embedded_trajectories')):
                    value = _migration_rewrite_wire(value, arg, local, depth + 1)
            elif kind in ('id', 'execution'):
                if w != 2:
                    raise ValueError('Invalid protobuf identity wire type')
                old = value.decode('utf-8')
                if kind == 'id':
                    domain = context['trajectory_map' if 'trajectory' in arg else 'conversation_map']
                    value = domain.get(old,old).encode('utf-8')
                elif old:
                    value = context['execution_ids'].setdefault(old, str(uuid.uuid4())).encode('utf-8')
            elif kind in ('step', 'gen'):
                offset = local['step_offset' if kind == 'step' else 'gen_offset']
                if w == 0:
                    # Negative signed sentinels (e.g. -1) must remain sentinels.
                    if value < (1 << 63):
                        value += offset
                elif w == 2 and arg:
                    packed = bytearray()
                    pos = 0
                    while pos < len(value):
                        index, pos = _migration_read_varint(value, pos)
                        packed += _migration_varint(index + offset if index < (1 << 63) else index)
                    value = bytes(packed)
                else:
                    raise ValueError('Invalid protobuf index wire type')
        out.append((n,w,value))
    return _migration_encode_wire(out)


def _migration_summary(source_cid, new_cid, target_account, context, step_count, title=None):
    conn = _migration_open_readonly(CONVERSATION_SUMMARIES_DB)
    try:
        cur = conn.execute('SELECT * FROM conversation_summaries WHERE conversation_id=?', (source_cid,))
        row = cur.fetchone()
        if row is None:
            raise ValueError('Source conversation has no summary')
        summary = dict(zip([d[0] for d in cur.description], row))
    finally:
        conn.close()
    if not isinstance(summary.get('raw_summary'), bytes):
        raise ValueError('Source summary has no supported raw_summary')
    raw = _migration_rewrite_wire(summary['raw_summary'], 'exa.jetski_cortex_pb.CascadeTrajectorySummary', context)
    fields = [f for f in _migration_parse_wire(raw) if f[0] not in (2, 4) and not (title is not None and f[0] == 1)]
    if title is not None:
        fields.append((1,2,title.encode('utf-8')))
    fields += [(2,0,step_count), (4,2,context['target_tid'].encode('utf-8'))]
    summary['raw_summary'] = _migration_encode_wire(fields)
    summary['conversation_id'] = new_cid
    if 'step_count' in summary:
        summary['step_count'] = step_count
    if title is not None:
        summary['title'] = title
    if target_account and 'app_data_dir' in summary:
        summary['app_data_dir'] = 'antigravity-instance2' if (target_account == 'instance_2' or norm_account(target_account) == get_secondary_account()) else 'antigravity'
    return summary


def _migration_merge_latest_summary(primary, latest):
    # A merged trajectory keeps the first source's identity/project/creation,
    # while the appended final segment supplies the latest state and indices.
    latest_numbers = {3,5,8,10,12,14,16,18,19,21,23,25,26,28,29,30}
    fields = [f for f in _migration_parse_wire(primary['raw_summary']) if f[0] not in latest_numbers]
    fields.extend(f for f in _migration_parse_wire(latest['raw_summary']) if f[0] in latest_numbers)
    result = dict(primary)
    result['raw_summary'] = _migration_encode_wire(fields)
    return result


def _migration_context(source_cid, source_tid, target_cid, target_tid):
    offsets = {'step_offset': 0, 'gen_offset': 0}
    return dict(offsets, id_map={source_cid: target_cid, source_tid: target_tid},
                trajectory_map={source_tid:target_tid},conversation_map={source_cid:target_cid},
                trajectory_contexts={source_tid:offsets},conversation_contexts={source_cid:offsets},
                reference_contexts={source_cid: offsets, source_tid: offsets}, execution_ids={}, target_tid=target_tid)


def _migration_rewrite_database(conn, context, target_cid, target_tid):
    tables = _migration_tables(conn)
    conn.execute('UPDATE trajectory_meta SET cascade_id=?,trajectory_id=?', (target_cid,target_tid))
    blob_types = {'gen_metadata': 'exa.cortex_pb.CortexStepGeneratorMetadata',
                  'executor_metadata': 'exa.cortex_pb.ExecutorMetadata',
                  'parent_references': 'exa.cortex_pb.CortexTrajectoryReference',
                  'trajectory_metadata_blob': 'exa.cortex_pb.CortexTrajectoryMetadata',
                  'battle_mode_infos': 'exa.cortex_pb.BattleModeInfo'}
    for table, message in blob_types.items():
        if table not in tables:
            continue
        cols = tables[table]
        key = 'id' if table == 'trajectory_metadata_blob' else 'idx'
        if 'data' not in cols or key not in cols:
            raise ValueError('Unsupported metadata schema: ' + table)
        for ident, data in conn.execute('SELECT ' + key + ',data FROM ' + table).fetchall():
            rewritten = _migration_rewrite_wire(data, message, context)
            if 'size' in cols:
                conn.execute('UPDATE ' + table + ' SET data=?,size=? WHERE ' + key + '=?', (rewritten,len(rewritten) if rewritten is not None else 0,ident))
            else:
                conn.execute('UPDATE ' + table + ' SET data=? WHERE ' + key + '=?', (rewritten,ident))
    step_blobs = {'metadata': 'exa.cortex_pb.CortexStepMetadata', 'render_info': 'exa.cortex_pb.StepRenderInfo', 'step_payload': 'gemini_coder.Step'}
    for idx, in conn.execute('SELECT idx FROM steps').fetchall():
        for col, message in step_blobs.items():
            if col in tables['steps']:
                data = conn.execute('SELECT ' + col + ' FROM steps WHERE idx=?', (idx,)).fetchone()[0]
                conn.execute('UPDATE steps SET ' + col + '=? WHERE idx=?', (_migration_rewrite_wire(data,message,context),idx))


def _migration_validate_target(record):
    conn = _migration_open_readonly(record['db_path'])
    try:
        info = _migration_inspect(conn,allow_embedded=record.get('allows_embedded',False))
        if info['cascade_id'] != record['target_id'] or info['trajectory_id'] != record['trajectory_id']:
            raise ValueError('Target identity verification failed')
        if info['counts'] != record['expected_counts']:
            raise ValueError('Target row count verification failed')
        if record['summary'].get('conversation_id') != record['target_id'] or record['expected_step_count'] != info['counts']['steps']:
            raise ValueError('Target summary count or conversation identity disagrees with its database')
        raw = _migration_parse_wire(record['summary']['raw_summary'])
        if not any(n == 2 and w == 0 and v == info['counts']['steps'] for n,w,v in raw):
            raise ValueError('Target raw summary step count verification failed')
        if not any(n == 4 and w == 2 and v == info['trajectory_id'].encode('utf-8') for n,w,v in raw):
            raise ValueError('Target summary identity verification failed')
    finally:
        conn.close()


def _migration_publish(records, source_ids, mode, backup_path):
    for record in records:
        _migration_validate_target(record)
    hook = globals().get('_migration_commit_hook')
    if hook is None:
        try:
            from migration_native_commit import commit_migration
            hook = commit_migration
        except ImportError as error:
            raise RuntimeError('Migration needs the native-owner commit hook; sources were preserved') from error
    for record in records:
        account = record.get('target_account')
        if account:
            assigned = assign_conversation_account(record['target_id'],account,action='add')
            if not isinstance(assigned,dict) or not assigned.get('success'):
                raise RuntimeError('Target account assignment failed')
    result = hook(records, list(source_ids), mode, backup_path)
    if not isinstance(result, dict) or not result.get('success'):
        raise RuntimeError((result or {}).get('error', 'Native migration commit failed') if isinstance(result, dict) else 'Native migration commit did not confirm success')
    if mode == 'move' and set(result.get('sources_archived',[])) != set(source_ids):
        raise RuntimeError('Native owner did not confirm archival of every source')
    return result


def create_safety_backup(conv_ids):
    """Snapshot every input and the summary index before any destructive commit."""
    ensure_dirs()
    if not conv_ids:
        raise ValueError('No conversations specified')
    paths = [(cid, _migration_path(cid)) for cid in conv_ids]
    if any(not os.path.isfile(path) for cid,path in paths):
        raise FileNotFoundError('A source conversation is missing')
    target = os.path.join(BACKUP_DIR, 'pre_migration_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex)
    os.mkdir(target)
    for cid, source in paths:
        _migration_snapshot(source, os.path.join(target,cid + '.db'))
        brain = os.path.join(BRAIN_DIR,cid)
        if os.path.exists(brain):
            shutil.copytree(brain,os.path.join(target,'brain_' + cid))
    _migration_snapshot(CONVERSATION_SUMMARIES_DB,os.path.join(target,'conversation_summaries.db'))
    return target


def clone_single_conversation(source_cid, new_cid=None, target_account=None, _defer_commit=False):
    """Build and verify a new conversation, publishing only through its owner."""
    ensure_dirs()
    new_cid = new_cid or str(uuid.uuid4())
    src_db, dst_db = _migration_path(source_cid), _migration_path(new_cid)
    if not os.path.isfile(src_db):
        raise FileNotFoundError(src_db)
    dst_brain = os.path.join(BRAIN_DIR,new_cid)
    if os.path.lexists(dst_db) or os.path.lexists(dst_brain):
        raise FileExistsError('Destination conversation already exists')
    _migration_snapshot(src_db,dst_db)
    conn = sqlite3.connect(dst_db)
    try:
        info = _migration_inspect(conn,allow_embedded=True)
        if info['cascade_id'] != source_cid:
            raise ValueError('Source identity does not match its filename')
        signature = _migration_signature(conn)
        target_tid = str(uuid.uuid4())
        context = _migration_context(source_cid,info['trajectory_id'],new_cid,target_tid)
        context['preserve_embedded_trajectories'] = True
        with conn:
            _migration_rewrite_database(conn,context,new_cid,target_tid)
        summary = _migration_summary(source_cid,new_cid,target_account,context,info['counts']['steps'])
    finally:
        conn.close()
    brain = os.path.join(BRAIN_DIR,source_cid)
    if os.path.exists(brain):
        # Copy literal transcript bytes; UUIDs in user content are not identities.
        shutil.copytree(brain,dst_brain)
    record = {'target_id':new_cid,'source_id':source_cid,'source_ids':[source_cid],
              'trajectory_id':target_tid,'allows_embedded':True,'summary':summary,'expected_step_count':info['counts']['steps'],
              'db_path':dst_db,'brain_path':dst_brain,'expected_counts':info['counts'],'target_account':target_account,
              'source_signatures':{source_cid:signature},'offsets':{source_cid:{'step_offset':0,'gen_offset':0}}}
    _migration_validate_target(record)
    if _defer_commit:
        return record
    backup = create_safety_backup([source_cid])
    _migration_publish([record],[source_cid],'copy',backup)
    return new_cid


def merge_conversations(conv_ids, target_title='Merged Project Timeline', target_account=None, _defer_commit=False):
    """Append supported trajectories without losing overlapping row indices."""
    if not conv_ids or len(set(conv_ids)) != len(conv_ids):
        raise ValueError('Specify distinct source conversations')
    # Every source is an immutable, WAL-aware snapshot before rebasing begins.
    backup = create_safety_backup(conv_ids)
    inputs = []
    try:
        for cid in conv_ids:
            conn = _migration_open_readonly(os.path.join(backup,cid + '.db'))
            try:
                info = _migration_inspect(conn)
                if info['cascade_id'] != cid:
                    raise ValueError('Source identity does not match its filename')
                info.update(cid=cid,conn=conn,signature=_migration_signature(conn))
                inputs.append(info)
            except Exception:
                conn.close()
                raise
        known = {'trajectory_meta','steps','gen_metadata','executor_metadata','parent_references','trajectory_metadata_blob','battle_mode_infos'}
        for item in inputs:
            for table,count in item['counts'].items():
                if table not in known and count:
                    raise ValueError('Cannot merge populated unsupported table: ' + table)
            if item['tables'] != inputs[0]['tables']:
                raise ValueError('Cannot merge conversations with different SQLite schemas')
        target_cid,target_tid = str(uuid.uuid4()),str(uuid.uuid4())
        dst_db = _migration_path(target_cid)
        dst_brain = os.path.join(BRAIN_DIR,target_cid)
        if os.path.lexists(dst_brain):
            raise FileExistsError(dst_brain)
        _migration_snapshot(os.path.join(backup,conv_ids[0] + '.db'),dst_db)
        id_map,reference_contexts,offsets = {},{},{}
        trajectory_map,conversation_map = {},{}
        trajectory_contexts,conversation_contexts = {},{}
        next_indices = {table:0 for table in ('steps','gen_metadata','executor_metadata','parent_references','battle_mode_infos')}
        for item in inputs:
            item['offsets'] = dict(next_indices)
            ref = {'step_offset':next_indices['steps'],'gen_offset':next_indices['gen_metadata']}
            offsets[item['cid']] = dict(ref)
            id_map[item['cid']] = target_cid
            id_map[item['trajectory_id']] = target_tid
            reference_contexts[item['cid']] = ref
            # Two input files sharing a trajectory ID cannot express distinct
            # index spaces in references; guessing would silently corrupt links.
            if item['trajectory_id'] in trajectory_contexts:
                raise ValueError('Cannot merge ambiguous duplicate trajectory identities')
            reference_contexts[item['trajectory_id']] = ref
            trajectory_map[item['trajectory_id']] = target_tid
            conversation_map[item['cid']] = target_cid
            trajectory_contexts[item['trajectory_id']] = ref
            conversation_contexts[item['cid']] = ref
            for table in next_indices:
                if table in item['tables']:
                    maximum = item['conn'].execute('SELECT MAX(idx) FROM ' + table).fetchone()[0]
                    if maximum is not None:
                        if not isinstance(maximum,int) or maximum < 0:
                            raise ValueError('Unsupported metadata index')
                        next_indices[table] += maximum + 1
        shared = {'id_map':id_map,'reference_contexts':reference_contexts,'execution_ids':{},'target_tid':target_tid,
                  'trajectory_map':trajectory_map,'conversation_map':conversation_map,
                  'trajectory_contexts':trajectory_contexts,'conversation_contexts':conversation_contexts}
        conn = sqlite3.connect(dst_db)
        try:
            with conn:
                for item in inputs:
                    context = dict(shared,**offsets[item['cid']])
                    if item is inputs[0]:
                        _migration_rewrite_database(conn,context,target_cid,target_tid)
                        continue
                    # Rewrite the secondary snapshot in memory, never its files.
                    scratch = sqlite3.connect(':memory:')
                    try:
                        item['conn'].backup(scratch)
                        _migration_rewrite_database(scratch,context,target_cid,target_tid)
                        for table in ('steps','gen_metadata','executor_metadata','parent_references','battle_mode_infos'):
                            if table not in item['tables']:
                                continue
                            cols = item['tables'][table]
                            index_pos = cols.index('idx')
                            sql = 'INSERT INTO ' + table + ' (' + ','.join(_migration_sql_name(c) for c in cols) + ') VALUES (' + ','.join('?' for c in cols) + ')'
                            for row in scratch.execute('SELECT * FROM ' + table).fetchall():
                                row = list(row)
                                row[index_pos] += item['offsets'][table]
                                conn.execute(sql,row)
                    finally:
                        scratch.close()
            counts = dict(inputs[0]['counts'])
            for table in ('steps','gen_metadata','executor_metadata','parent_references','battle_mode_infos'):
                if table in counts:
                    counts[table] = sum(item['counts'][table] for item in inputs)
            if _migration_inspect(conn)['counts'] != counts:
                raise ValueError('Merge did not preserve every source row')
        finally:
            conn.close()
        os.mkdir(dst_brain)
        for item in inputs:
            cid = item['cid']
            brain = os.path.join(backup,'brain_' + cid)
            if item is inputs[0] and os.path.isdir(brain):
                shutil.copytree(brain,dst_brain,dirs_exist_ok=True)
            archive = os.path.join(dst_brain,'merged_sources',cid)
            os.makedirs(archive,exist_ok=False)
            # Preserve each source's original singleton metadata and brain too.
            shutil.copy2(os.path.join(backup,cid + '.db'),os.path.join(archive,'trajectory.db'))
            if os.path.isdir(brain):
                shutil.copytree(brain,os.path.join(archive,'brain'))
        context = dict(shared,**offsets[conv_ids[0]])
        summary = _migration_summary(conv_ids[0],target_cid,target_account,context,counts['steps'],target_title)
        if len(conv_ids) > 1:
            latest_context = dict(shared,**offsets[conv_ids[-1]])
            latest = _migration_summary(conv_ids[-1],target_cid,target_account,latest_context,counts['steps'],target_title)
            summary = _migration_merge_latest_summary(summary,latest)
        record = {'target_id':target_cid,'source_ids':list(conv_ids),'trajectory_id':target_tid,
                  'summary':summary,'expected_step_count':counts['steps'],'db_path':dst_db,'brain_path':dst_brain,
                  'expected_counts':counts,'offsets':offsets,'target_account':target_account,
                  'source_signatures':{item['cid']:item['signature'] for item in inputs}}
        _migration_validate_target(record)
        if _defer_commit:
            return record
        _migration_publish([record],conv_ids,'copy',backup)
        return target_cid
    finally:
        for item in inputs:
            item['conn'].close()


def setup_dual_sync(account_a, account_b, sync_pairs):
    """Register dual-sync pair mappings in sync_manifest.json."""
    ensure_dirs()
    manifest = {}
    if os.path.exists(SYNC_MANIFEST_PATH):
        try:
            with open(SYNC_MANIFEST_PATH, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    pair_key = f"{account_a}<->{account_b}"
    if pair_key not in manifest:
        manifest[pair_key] = {
            'account_a': account_a,
            'account_b': account_b,
            'pairs': [],
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'auto_sync': True
        }

    for p in sync_pairs:
        manifest[pair_key]['pairs'].append(p)

    with open(SYNC_MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

def migrate_conversations(conv_ids, source_account, target_account, mode='copy', structure='separate', dual_sync=False, project_id=None):
    """Publish a fully verified batch. Move archives sources through their owner.

    Source database/brain files are retained for recovery and parent references;
    no SQLite writer files are ever removed by a migration.
    """
    backup_path = None
    records = []
    try:
        if not conv_ids or len(set(conv_ids)) != len(conv_ids):
            raise ValueError('Specify distinct source conversations')
        if mode not in ('copy','move') or structure not in ('separate','merge'):
            raise ValueError('Unsupported migration mode or structure')
        # A missing source, failed snapshot, or brain copy aborts the whole batch.
        backup_path = create_safety_backup(conv_ids)
        if structure == 'merge':
            record = merge_conversations(conv_ids,target_account=target_account,_defer_commit=True)
            if not isinstance(record,dict):
                raise ValueError('Merge did not produce a verified target')
            records.append(record)
        else:
            for cid in conv_ids:
                record = clone_single_conversation(cid,target_account=target_account,_defer_commit=True)
                if not isinstance(record,dict):
                    raise ValueError('Clone did not produce a verified target')
                records.append(record)
        # Fail before asking the native owner to publish/archive anything if any
        # destination, source count, summary, or requested manifest update fails.
        for record in records:
            _migration_validate_target(record)
        if dual_sync:
            pairs = [{'source':r.get('source_id',r['source_ids']),'target':r['target_id']} for r in records]
            setup_dual_sync(source_account,target_account,pairs)
        if project_id:
            assigned = sync_project_to_account(project_id,target_account,include_conversations=False)
            if not isinstance(assigned,dict) or not assigned.get('success'):
                raise RuntimeError('Project assignment failed')
        committed = _migration_publish(records,conv_ids,mode,backup_path)
        results = [dict({'source_ids':r['source_ids'],'target_id':r['target_id'],
                         'type':'merged' if structure == 'merge' else 'cloned',
                         'expected_step_count':r['expected_step_count']},
                        **({'source_id':r['source_id']} if 'source_id' in r else {})) for r in records]
        return {'success':True,'mode':mode,'structure':structure,'migrated_count':len(records),
                'results':results,'backup_path':backup_path,
                'source_action':'archived' if mode == 'move' else 'retained',
                'sources_archived':committed.get('sources_archived',[])}
    except Exception as error:
        # A native publication error can leave recoverable unregistered targets.
        # Never clean up a target after the owner might have opened it, or remove
        # a source. Report the partial artifacts explicitly for recovery.
        return {'success':False,'mode':mode,'structure':structure,'migrated_count':0,
                'error':str(error),'backup_path':backup_path,
                'created_targets':[r['target_id'] for r in records],
                'source_action':'files_retained','archival_status':'unconfirmed'}


def delete_conversation(conv_id):
    """Safely delete a conversation database and its brain folder."""
    db_path = os.path.join(CONVERSATIONS_DIR, f"{conv_id}.db")
    for f in [db_path, f"{db_path}-wal", f"{db_path}-shm"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
    brain_path = os.path.join(BRAIN_DIR, conv_id)
    if os.path.exists(brain_path):
        try:
            shutil.rmtree(brain_path, ignore_errors=True)
        except Exception:
            pass

    # Remove from conversation_summaries.db
    if os.path.exists(CONVERSATION_SUMMARIES_DB):
        try:
            conn = sqlite3.connect(CONVERSATION_SUMMARIES_DB, timeout=30.0)
            cur = conn.cursor()
            cur.execute("DELETE FROM conversation_summaries WHERE conversation_id = ?", (conv_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass

def is_account2(email):
    if not email:
        return False
    norm = str(email).lower().strip()
    return norm in ('instance_2', 'secondary_account', 'user2@example.com') or 'account2' in norm or 'secondary' in norm

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Antigravity Migration & Profile Isolation Engine")
    parser.add_argument('--list', action='store_true', help='List all conversations')
    parser.add_argument('--projects', action='store_true', help='List all projects')
    parser.add_argument('--tasks', action='store_true', help='List all scheduled tasks')
    parser.add_argument('--allowed-convs', help='List allowed conversation IDs for account')
    parser.add_argument('--check-task-guard', help='Check if task is permitted to execute')
    parser.add_argument('--run-task', help='Run scheduled task with its designated quota_account credentials')
    parser.add_argument('--account', help='Account email or instance alias to check against')
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_conversations(), indent=2, ensure_ascii=False))
    elif args.projects:
        print(json.dumps(list_projects(), indent=2, ensure_ascii=False))
    elif args.tasks:
        print(json.dumps(list_scheduled_tasks(), indent=2, ensure_ascii=False))
    elif args.allowed_convs:
        print(json.dumps(get_allowed_conversations(args.allowed_convs), indent=2, ensure_ascii=False))
    elif args.check_task_guard:
        guard_res = check_task_guard(args.check_task_guard, current_account=args.account)
        print(json.dumps(guard_res, indent=2, ensure_ascii=False))
        sys.exit(0 if guard_res.get("allowed") else 1)
    elif args.run_task:
        res = run_guarded_task(args.run_task)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        sys.exit(0 if res.get("success") else 1)
    else:
        print("Antigravity Migration & Profile Isolation Engine Ready.")
