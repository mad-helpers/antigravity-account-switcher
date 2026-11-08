"""Regression: a broken conversations store must not blank the injected plugin."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import sync_daemon


class Boom:
    @staticmethod
    def get_allowed_conversations(_):
        raise FileExistsError("dangling junction")


def test_safe_allowed_convs_swallows_store_errors():
    assert sync_daemon._safe_allowed_convs(Boom, "a@b.c") == []


def test_no_undefined_names():
    import migration_engine, server
    assert hasattr(migration_engine, "platform") and hasattr(server, "urllib")


if __name__ == "__main__":
    test_safe_allowed_convs_swallows_store_errors(); test_no_undefined_names(); print("ok")
