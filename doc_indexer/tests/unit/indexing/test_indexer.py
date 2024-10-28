from typing import Any
from unittest.mock import Mock, patch

import pytest
from indexing.indexer import MarkdownIndexer, create_chunks
from langchain_core.documents import Document


@pytest.fixture(scope="session")
def fixtures_path(root_tests_path) -> str:
    return f"{root_tests_path}/unit/fixtures"


@pytest.fixture
def mock_embedding():
    return Mock()


@pytest.fixture
def mock_connection():
    return Mock()


@pytest.fixture
def mock_hana_db():
    with patch("indexing.indexer.HanaDB") as mock:
        yield mock


@pytest.fixture
def indexer(mock_embedding, mock_connection, mock_hana_db):
    return MarkdownIndexer(
        docs_path="",
        embedding=mock_embedding,
        connection=mock_connection,
        table_name="test_table",
    )


@pytest.fixture
def sample_documents() -> list[Document]:
    return [
        Document(
            page_content="""
            # Header
            Content 0""".strip()
        ),
        Document(
            page_content="""
            # Header 1
            Content 1
            ## Header 2
            Content 2
            # Header one
            Content 3""".strip()
        ),
        Document(
            page_content="""
            # Another Header
            Some content
            ## Subheader
            More content""".strip()
        ),
        Document(page_content="No headers here, just plain content."),
    ]


@pytest.mark.parametrize(
    "input_docs, headers_to_split_on, expected_chunks, expected_exception",
    [
        (
            "sample_documents",
            [("#", "Header 1")],
            [
                "# Header\nContent 0".strip(),
                "# Header 1\n" "Content 1\n" "## Header 2\n" "Content 2",
                "# Header one\nContent 3",
                "# Another Header\nSome content\n## Subheader\nMore content",
                "No headers here, just plain content.",
            ],
            None,
        ),
        (
            "sample_documents",
            [("#", "Header 1"), ("##", "Header 2")],
            [
                "# Header\nContent 0",
                "# Header 1\nContent 1",
                "## Header 2\nContent 2",
                "# Header one\nContent 3",
                "# Another Header\nSome content",
                "## Subheader\nMore content",
                "No headers here, just plain content.",
            ],
            None,
        ),
        # Edge cases
        ([], [("#", "Header 1")], [], None),
        (
            [Document(page_content="No headers here, just plain content.")],
            [("#", "Header 1")],
            ["No headers here, just plain content."],
            None,
        ),
        # error cases
        (None, [("#", "Header 1")], None, TypeError),
        ("Not a list", [("#", "Header 1")], None, AttributeError),
        ([None], [("#", "Header 1")], None, AttributeError),
        ([{"not": "a document"}], [("#", "Header 1")], None, AttributeError),
    ],
)
def test_create_chunks(
    sample_documents: list[Document],
    input_docs: Any,
    headers_to_split_on: list[tuple],
    expected_chunks: list[str],
    expected_exception: type,
) -> None:
    if input_docs == "sample_documents":
        input_docs = sample_documents

    if expected_exception:
        with pytest.raises(expected_exception):
            create_chunks(input_docs, headers_to_split_on)
    else:
        result = create_chunks(input_docs, headers_to_split_on)
        assert len(result) == len(expected_chunks)
        for res, exp in zip(result, expected_chunks, strict=False):
            assert res.page_content.strip() == exp.strip()


@pytest.mark.parametrize(
    "test_case,docs_path,expected_docs_number, expected_exception",
    [
        (
            "Multiple documents",
            "./test_docs",
            4,
            None,
        ),
        (
            "Double nested subdirectories",
            "./double_nested_dirs",
            2,
            None,
        ),
        (
            "No subdirectories",
            "./single_doc",
            1,
            None,
        ),
        (
            "Empty directory",
            "./empty_dir",
            0,
            None,
        ),
        (
            "Non-existent directory",
            "./non_existent_dir",
            0,
            FileNotFoundError,
        ),
    ],
)
def test_load_documents(
    fixtures_path,
    indexer,
    test_case,
    docs_path,
    expected_docs_number,
    expected_exception,
) -> None:
    indexer.docs_path = fixtures_path + "/" + docs_path
    if expected_exception:
        with pytest.raises(expected_exception):
            indexer._load_documents()
    else:
        result = indexer._load_documents()
        assert len(result) == expected_docs_number, f"Failed case: {test_case}"


@pytest.mark.parametrize(
    "test_case,headers_to_split_on,loaded_docs,expected_chunks,delete_error,add_error,expected_exception",
    [
        (
            "Default header",
            None,
            [
                Document(
                    page_content="# My Header 1\nContent",
                )
            ],
            [
                Document(
                    page_content="# My second Header 1 \nContent",
                )
            ],
            None,
            None,
            None,
        ),
        (
            "Custom headers",
            [("##", "Header2")],
            [
                Document(
                    page_content="# H1\n## H2\nContent",
                )
            ],
            [
                Document(
                    page_content="# H1\n", metadata={"source": "/test/docs/file1.md"}
                ),
                Document(
                    page_content="## H2\nContent",
                ),
            ],
            None,
            None,
            None,
        ),
        (
            "Delete error",
            None,
            [],
            [],
            Exception("Delete error"),
            None,
            Exception,
        ),
        (
            "Add documents error",
            None,
            [],
            [],
            None,
            Exception("Add documents error"),
            Exception,
        ),
    ],
)
def test_index(
    indexer,
    mock_hana_db,
    test_case,
    headers_to_split_on,
    loaded_docs,
    expected_chunks,
    delete_error,
    add_error,
    expected_exception,
) -> None:
    indexer.db.delete.side_effect = delete_error
    indexer.db.add_documents.side_effect = add_error

    with patch.object(indexer, "_load_documents", return_value=loaded_docs), patch(
        "indexing.indexer.create_chunks", return_value=expected_chunks
    ) as mock_create_chunks:
        indexer.headers_to_split_on = headers_to_split_on
        if expected_exception:
            with pytest.raises(expected_exception):
                indexer.index()
        else:
            indexer.index()

            mock_create_chunks.assert_called_once_with(loaded_docs, headers_to_split_on)
            indexer.db.delete.assert_called_once_with(filter={})
            indexer.db.add_documents.assert_called_once_with(expected_chunks)

    if delete_error:
        assert str(delete_error) in str(indexer.db.delete.side_effect)
    if add_error:
        assert str(add_error) in str(indexer.db.add_documents.side_effect)
