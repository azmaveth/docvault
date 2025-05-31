"""
Test collections functionality.
"""

import json

import pytest
from click.testing import CliRunner

from docvault.cli.collection_commands import collection
from docvault.db.operations import add_document
from docvault.models import collections


class TestCollectionsModel:
    """Test collections model operations."""

    def test_create_collection(self, test_db):
        """Test creating a collection."""
        collection_id = collections.create_collection(
            name="Test Collection",
            description="A test collection",
            default_tags=["python", "test"],
        )

        assert collection_id > 0

        # Verify collection was created
        coll = collections.get_collection(collection_id)
        assert coll is not None
        assert coll["name"] == "Test Collection"
        assert coll["description"] == "A test collection"
        assert coll["default_tags"] == ["python", "test"]

    def test_create_duplicate_collection(self, test_db):
        """Test creating a collection with duplicate name."""
        collections.create_collection("Duplicate Test")

        with pytest.raises(ValueError, match="already exists"):
            collections.create_collection("Duplicate Test")

    def test_add_document_to_collection(self, test_db):
        """Test adding documents to a collection."""
        # Create collection
        coll_id = collections.create_collection("Test Collection")

        # Add document
        doc_id = add_document(
            url="https://example.com/doc1",
            title="Test Doc",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        # Add to collection
        success = collections.add_document_to_collection(coll_id, doc_id)
        assert success is True

        # Verify document is in collection
        docs = collections.get_collection_documents(coll_id)
        assert len(docs) == 1
        assert docs[0]["id"] == doc_id

    def test_collection_document_ordering(self, test_db):
        """Test that documents maintain order in collections."""
        coll_id = collections.create_collection("Ordered Collection")

        # Add documents in specific order
        doc_ids = []
        for i in range(3):
            doc_id = add_document(
                url=f"https://example.com/doc{i}",
                title=f"Doc {i}",
                html_path="/tmp/test.html",
                markdown_path="/tmp/test.md",
                version="1.0",
            )
            doc_ids.append(doc_id)
            collections.add_document_to_collection(coll_id, doc_id, position=i)

        # Get documents and verify order
        docs = collections.get_collection_documents(coll_id)
        assert len(docs) == 3
        for i, doc in enumerate(docs):
            assert doc["id"] == doc_ids[i]
            assert doc["position"] == i

    def test_get_document_collections(self, test_db):
        """Test finding which collections contain a document."""
        doc_id = add_document(
            url="https://example.com/shared",
            title="Shared Doc",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        # Create multiple collections
        coll1_id = collections.create_collection("Collection 1")
        coll2_id = collections.create_collection("Collection 2")

        # Add document to both
        collections.add_document_to_collection(coll1_id, doc_id)
        collections.add_document_to_collection(coll2_id, doc_id)

        # Find collections containing document
        colls = collections.get_document_collections(doc_id)
        assert len(colls) == 2
        coll_names = [c["name"] for c in colls]
        assert "Collection 1" in coll_names
        assert "Collection 2" in coll_names


class TestCollectionCommands:
    """Test collection CLI commands."""

    def test_create_command(self, test_db):
        """Test collection create command."""
        runner = CliRunner()

        result = runner.invoke(
            collection,
            [
                "create",
                "Test Collection",
                "--description",
                "A test collection",
            ],
        )
        
        assert result.exit_code == 0
        assert "Created collection 'Test Collection'" in result.output

    def test_list_command(self, test_db):
        """Test collection list command."""
        # Create a collection
        collections.create_collection("List Test", description="For listing")

        runner = CliRunner()
        result = runner.invoke(collection, ["list"])

        assert result.exit_code == 0
        assert "List Test" in result.output
        assert "For listing" in result.output

    def test_show_command(self, test_db):
        """Test collection show command."""
        # Create collection and add document
        coll_id = collections.create_collection("Show Test")
        doc_id = add_document(
            url="https://example.com/doc",
            title="Test Document",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )
        collections.add_document_to_collection(coll_id, doc_id)

        runner = CliRunner()
        result = runner.invoke(collection, ["show", "Show Test"])

        assert result.exit_code == 0
        assert "Show Test" in result.output
        assert "Test Document" in result.output

    def test_add_remove_commands(self, test_db):
        """Test adding and removing documents from collections."""
        # Create collection and document
        collections.create_collection("Add/Remove Test")
        doc_id = add_document(
            url="https://example.com/doc",
            title="Test Doc",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        runner = CliRunner()

        # Add document
        result = runner.invoke(collection, ["add", "Add/Remove Test", str(doc_id)])
        assert result.exit_code == 0
        assert "Added 1 document(s)" in result.output

        # Remove document
        result = runner.invoke(collection, ["remove", "Add/Remove Test", str(doc_id)])
        assert result.exit_code == 0
        assert "Removed 1 document(s)" in result.output

    def test_json_output(self, test_db):
        """Test JSON output format."""
        collections.create_collection("JSON Test")

        runner = CliRunner()
        result = runner.invoke(collection, ["list", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert data["count"] >= 1
        assert any(c["name"] == "JSON Test" for c in data["collections"])


class TestCollectionSearch:
    """Test search integration with collections."""

    def test_search_by_collection_filter(self, test_db):
        """Test that search properly filters by collection."""
        # Create collection
        coll_id = collections.create_collection("Search Test")

        # Add documents - one in collection, one not
        doc1_id = add_document(
            url="https://example.com/in-collection",
            title="In Collection",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )
        doc2_id = add_document(
            url="https://example.com/not-in-collection",
            title="Not In Collection",
            html_path="/tmp/test.html",
            markdown_path="/tmp/test.md",
            version="1.0",
        )

        # Add only doc1 to collection
        collections.add_document_to_collection(coll_id, doc1_id)

        # Get document IDs for the collection
        doc_ids = collections.search_documents_by_collection(coll_id)

        assert len(doc_ids) == 1
        assert doc_ids[0] == doc1_id
        assert doc2_id not in doc_ids
