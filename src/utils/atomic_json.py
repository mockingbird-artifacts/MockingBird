import json
import os
import tempfile


def dump_json_atomic(obj, path, indent=4):
    """Write JSON to `path` atomically: the data goes to a temporary file in the same directory which is fsync'ed and then
    renamed over the target, so a crash or a full disk during the write leaves the previous file intact (a plain
    open(path, 'w') truncates first and a failed write leaves a truncated, unparseable file)."""
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(obj, f, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
