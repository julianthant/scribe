from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AttachmentBase(BaseModel):
    """Schema for Microsoft Graph API attachment response"""

    odata_context: Annotated[str, Field(alias="@odata.context")]
    odata_type: Annotated[str, Field(alias="@odata.type")]
    id: str
    lastModifiedDateTime: datetime
    name: str
    contentType: str
    size: int
    isInline: bool
    contentId: str | None
    contentLocation: str | None
    contentBytes: str

    model_config = ConfigDict(populate_by_name=True)