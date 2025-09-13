from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

class EmailBase(BaseModel):
    """Schema for Microsoft Graph API message response"""

    odata_context: Annotated[str, Field(alias="@odata.context")]
    odata_etag: Annotated[str, Field(alias="@odata.etag")]
    id: str
    createdDateTime: datetime
    lastModifiedDateTime: datetime
    changeKey: str
    categories: list[str]
    receivedDateTime: datetime
    sentDateTime: datetime
    hasAttachments: bool
    internetMessageId: str
    subject: str
    bodyPreview: str
    importance: Literal["low", "normal", "high"]
    parentFolderId: str
    conversationId: str
    isDeliveryReceiptRequested: bool
    isReadReceiptRequested: bool
    isRead: bool
    isDraft: bool
    webLink: str
    inferenceClassification: Literal["focused", "other"]
    body: dict[str, str]
    sender: dict[str, dict[str, str]]
    from_: Annotated[dict[str, dict[str, str]], Field(alias="from")]
    toRecipients: list[dict[str, dict[str, str]]]
    ccRecipients: list[dict[str, dict[str, str]]]
    bccRecipients: list[dict[str, dict[str, str]]]
    replyTo: list[dict[str, dict[str, str]]]
    flag: dict[str, str]

    model_config = ConfigDict(populate_by_name=True)