import logging
from typing import Any

from app.graph.client import GraphClient, GraphConflict
from app.pipeline.workbook import append_record, message_ids

logger = logging.getLogger(__name__)


async def sheet_contains(graph: GraphClient, path: str, message_id: str) -> bool:
    item = await graph.workbook_item(path)
    if item is None:
        return False
    data = await graph.download_item(str(item["id"]))
    return message_id in message_ids(data)


async def append_row(graph: GraphClient, path: str, record: dict[str, Any]) -> bool:
    """Upload one row. Returns False when the message id was already in the workbook."""
    for _attempt in range(3):
        item = await graph.workbook_item(path)
        if item is None:
            created = append_record(None, record)
            if created is None:
                return False
            try:
                await graph.create_workbook(path, created)
            except GraphConflict:
                logger.info(
                    "workbook appeared while creating message_id=%s; retrying",
                    record["message_id"],
                )
                continue
            logger.info("created workbook and appended message_id=%s", record["message_id"])
            return True
        data = await graph.download_item(str(item["id"]))
        updated = append_record(data, record)
        if updated is None:
            logger.info("workbook already has message_id=%s", record["message_id"])
            return False
        etag = item.get("eTag")
        try:
            await graph.upload_item(
                str(item["id"]),
                updated,
                etag if isinstance(etag, str) else None,
            )
        except GraphConflict:
            logger.info(
                "workbook changed while appending message_id=%s; retrying",
                record["message_id"],
            )
            continue
        logger.info(
            "appended message_id=%s model=%s duration=%s",
            record["message_id"],
            record["model"],
            record["duration_seconds"],
        )
        return True
    raise GraphConflict(412, "workbook_conflict")
