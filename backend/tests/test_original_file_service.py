import pytest

from gridfs.errors import NoFile

from app.services import original_file_service


class _FilesCollection:
    def __init__(self, items):
        self.items = items

    def find(self, *_args, **_kwargs):
        async def iterate():
            for item in self.items:
                yield item

        return iterate()


class _Database:
    def __init__(self, items):
        self.items = items

    def __getitem__(self, _name):
        return _FilesCollection(self.items)


@pytest.mark.asyncio
async def test_delete_original_file_ignores_missing_gridfs_file(monkeypatch):
    file_id = original_file_service.ObjectId()
    deleted = []

    class Bucket:
        async def delete(self, requested_id):
            deleted.append(requested_id)
            raise NoFile("file not found")

    monkeypatch.setattr(original_file_service, "document_files_bucket", Bucket)
    monkeypatch.setattr(
        original_file_service,
        "get_database",
        lambda: _Database([{"_id": file_id}]),
    )

    await original_file_service.delete_original_file("document-1", str(file_id))

    assert deleted == [file_id]


@pytest.mark.asyncio
async def test_delete_original_file_propagates_storage_errors(monkeypatch):
    file_id = original_file_service.ObjectId()

    class Bucket:
        async def delete(self, _requested_id):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(original_file_service, "document_files_bucket", Bucket)
    monkeypatch.setattr(
        original_file_service,
        "get_database",
        lambda: _Database([{"_id": file_id}]),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await original_file_service.delete_original_file("document-1")
