import inspect
from dataclasses import dataclass, field
from enum import StrEnum

import Utils
from models.curation import Curation
from models.file_detail import FileDetail
from models.message import Message
from models.model import Model
from models.nav_ref import NavRef
from typing import Optional
from PySide.QtCore import Qt, QAbstractListModel
from models.user_summary import UserSummary


class VersionFollow(StrEnum):
    LOCKED = "Locked"
    ACTIVE = "Active"


class Protection(StrEnum):
    LISTED = "Listed"
    UNLISTED = "Unlisted"
    PIN = "Pin"
    DIRECT = "Direct"


# NOTE: this are called 'shared-models' in the API and database for legacy reasons
@dataclass(order=True)
class ShareLink:
    _id: str
    createdAt: int
    updatedAt: int
    versionFollowing: Optional[VersionFollow]
    userId: str
    cloneModelId: str
    model: Model
    title: str
    description: str
    canViewModel: bool
    canViewModelAttributes: bool
    canUpdateModel: bool
    # export model permissions
    canExportFCStd: bool
    canExportSTEP: bool
    canExportSTL: bool
    canExportOBJ: bool
    canDownloadDefaultModel: bool  # "model" means "original file" in this context
    isActive: bool
    isSystemGenerated: Optional[bool]
    isThumbnailGenerated: Optional[bool]
    thumbnailUrl: str  # can be None or empty also
    fileDetail: FileDetail
    curation: Curation
    protection: Protection
    showInPublicGallery: Optional[bool] = None  # deprecated
    pin: Optional[str] = None
    directSharedTo: Optional[list[UserSummary]] = field(
        default_factory=list, repr=False
    )
    # TODO: figure out support for the following fields when needed:
    # messages: list[Message] = field(default_factory=list, repr=False)
    # messagesParticipants: list[UserSummary] = field(default_factory=list, repr=False)

    def __post_init__(self):
        self.model = Model(**self.model)
        self.fileDetail = FileDetail(**self.fileDetail)
        self.curation = Curation(**self.curation)
        self.directSharedTo = Utils.convert_to_class_list(
            self.directSharedTo, UserSummary
        )

    @classmethod
    def from_json(cls, json_data):
        return Utils.import_json_forgiving_of_extra_fields(cls, json_data)


class PublicShareLinkListModel(QAbstractListModel):

    ShareLinkRole = Qt.UserRole + 1

    def __init__(self, *args, sharelinks=None, **kwargs):
        super(PublicShareLinkListModel, self).__init__(*args, **kwargs)
        self.sharelink_list = sharelinks or []

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return self.sharelink_list[index.row()].name
        elif role == self.ShareLinkRole:
            return self.sharelink_list[index.row()]

    def rowCount(self, index):
        return len(self.sharelink_list)
