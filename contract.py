"""Each tool's and task's typed input and output: declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    READ_ARCHIVE_REQUEST = "read_archive_request"
    WRITE_MANIFEST = "write_manifest"


class Task(Enum):
    BUILD_ARCHIVE_MANIFEST = "build-archive-manifest"


@dataclass
class ArchiveManifestInput(Output):
    fixture_directory: Annotated[
        str,
        "Workspace-relative directory containing the files to consider.",
    ]
    include_patterns: Annotated[
        list[str],
        "Path glob patterns selecting files; an empty list selects every regular file.",
    ]
    exclude_patterns: Annotated[
        list[str],
        "Path glob patterns removed after includes are applied.",
    ]


@dataclass
class ArchiveFile(Output):
    path: Annotated[
        str,
        "Normalized fixture-relative file path using '/' separators.",
    ]
    size: Annotated[int, "File size in bytes."]
    sha256: Annotated[str, "Lowercase hexadecimal SHA-256 digest of the file bytes."]


@dataclass
class ArchiveManifestOutput(Output):
    entries: Annotated[
        list[ArchiveFile],
        "Selected files in ascending lexical path order.",
    ]


@dataclass
class ReadArchiveRequestInput(Output):
    task: Annotated[ArchiveManifestInput, "The archive-manifest task to inspect."]


@dataclass
class ReadArchiveRequestOutput(Output):
    fixture_directory: str
    include_patterns: list[str]
    exclude_patterns: list[str]
    available_files: Annotated[
        list[ArchiveFile],
        "Every available regular file, before include and exclude patterns are applied.",
    ]


@dataclass
class WriteManifestInput(Output):
    task: Annotated[ArchiveManifestInput, "The task input copied exactly as given."]
    entries: Annotated[
        list[ArchiveFile],
        "The final selected manifest entries in ascending lexical path order.",
    ]


@dataclass
class WriteManifestOutput(Output):
    report_path: Annotated[str, "The report path written relative to the workspace."]
    report: ArchiveManifestOutput


TOOLS = {
    Tool.READ_ARCHIVE_REQUEST: (ReadArchiveRequestInput, ReadArchiveRequestOutput),
    Tool.WRITE_MANIFEST: (WriteManifestInput, WriteManifestOutput),
}

TASKS = {
    Task.BUILD_ARCHIVE_MANIFEST: (ArchiveManifestInput, ArchiveManifestOutput),
}
