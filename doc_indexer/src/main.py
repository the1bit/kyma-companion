from indexing.indexer import MarkdownIndexer
from utils.hana import create_hana_connection
from utils.models import (
    create_openai_embedding,
)
from utils.settings import (
    DATABASE_URL,
    DATABASE_USER,
    DATABASE_PASSWORD,
    EMBEDDING_MODEL_DEPLOYMENT_ID,
    DATABASE_PORT,
)


def main():
    docs_path = "../data/kyma_os_docs"
    # init embedding model
    embeddings_model = create_openai_embedding(EMBEDDING_MODEL_DEPLOYMENT_ID)
    # setup connection to Hana Cloud DB
    hana_conn = create_hana_connection(
        DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD
    )

    indexer = MarkdownIndexer(docs_path, embeddings_model, hana_conn)
    indexer.index()


if __name__ == "__main__":
    main()
