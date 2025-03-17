# Add the project root directory to sys.path to ensure imports work correctly
import os
import re
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

# get openai key
from core.config import Config
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex, StorageContext, SimpleDirectoryReader


# Step 4: Extract Metadata from Filenames
def extract_metadata_from_filename(filename):
    filename = os.path.basename(filename)
    metadata_part = filename.rsplit(".", 1)[0]  # Remove file extension
    metadata = re.split(r"[_-]", metadata_part)  # Split on _ or - to get metadata parts
    return metadata

# load documents
documents = SimpleDirectoryReader("sources/").load_data()

# Assign extracted metadata to each document
for doc in documents:
    filename = doc.metadata.get("file_name", "unknown.pdf")
    metadata_tags = extract_metadata_from_filename(filename)
    doc.metadata = {
        "tags": metadata_tags,
        "source": filename
    }

# Setting qdrant keys
qdrant_url = Config.QDRANT_URL
qdrant_api_key = Config.QDRANT_API_KEY

# Initialize Qdrant client
client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=60)

# collection name
qdrant_collection_name = 'teachers_guides'

# Getting existing collections
collections = client.get_collections().collections
collection_names = [collection.name for collection in collections]
# Create collection if it doesn't exist   
if qdrant_collection_name not in collection_names:
    client.create_collection(
        collection_name=qdrant_collection_name,
        vectors_config=VectorParams(size=1536,distance=Distance.COSINE),
    )
    vector_store = QdrantVectorStore(client=client, collection_name=qdrant_collection_name)
    # Create storage context with Qdrant
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    # put into vector store index (use OpenAIEmbeddings by default)
    index = VectorStoreIndex(
        documents,
        storage_context=storage_context,
        model="text-embedding-ada-002"
        )

    print(f"Data indexed and saved to Qdrant collection '{qdrant_collection_name}'.")
else:
    print(f"Collection already exists.")

if True:
    vector_store = QdrantVectorStore(client=client, collection_name=qdrant_collection_name)
    #create a vector index from the vector store
    index = VectorStoreIndex.from_vector_store(vector_store)
    query_engine = index.as_query_engine()
    response = query_engine.query("What are the outcomes learning outcomes of students learning the structure of plant and animal cells?")
    print(response)