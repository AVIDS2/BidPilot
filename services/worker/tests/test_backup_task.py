"""Test the backup_database Celery Beat task."""
from unittest.mock import patch, MagicMock

from app.tasks import backup_database


def test_backup_database_success():
    """backup_database should return ok when subprocess succeeds."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Backup complete"

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = backup_database()

    assert result["status"] == "ok"
    mock_run.assert_called_once()
    # Verify the command includes backup.py
    args = mock_run.call_args[0][0]
    assert "backup.py" in args[-2] or any("backup.py" in str(a) for a in args)


def test_backup_database_failure():
    """backup_database should return error when subprocess fails."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Backup error"

    with patch("subprocess.run", return_value=mock_result):
        result = backup_database()

    assert result["status"] == "error"
    assert "Backup error" in result["output"]


def test_backup_database_exception():
    """backup_database should handle exceptions gracefully."""
    with patch("subprocess.run", side_effect=Exception("No disk space")):
        result = backup_database()

    assert result["status"] == "error"
    assert "No disk space" in result["detail"]
