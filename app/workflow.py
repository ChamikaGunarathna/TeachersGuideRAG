import os
import asyncio
import logging
# imports for workflow
from llama_index.core.workflow import (
    StartEvent, StopEvent, Workflow, step, Event,
    )
# imports for OpenAI services
from llama_index.llms.openai import OpenAI

# imports for qdrant vector db
from qdrant_client import QdrantClient
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex

# imports for prompting
from llama_index.core import PromptTemplate
from llama_index.core.retrievers import BaseRetriever
from llama_index.core import get_response_synthesizer
from llama_index.core.response_synthesizers import BaseSynthesizer

# imports for custom query engine
from llama_index.core.query_engine import CustomQueryEngine

# imports for API keys
from app.core.config import Config

# setup Arize Phoenix 
import llama_index.core

PHOENIX_API_KEY = Config.PHOENIX_API_KEY
os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"api_key={PHOENIX_API_KEY}"
llama_index.core.set_global_handler(
    "arize_phoenix",
    endpoint="https://llamatrace.com/v1/traces"
)

# setup logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# setup prompts
qa_prompt = PromptTemplate(
    "Context information is below.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given the context information and not prior knowledge, "
    "answer the query.\n"
    "Query: {query_str}\n"
    "Answer: "
)

# Setting qdrant keys
qdrant_url = Config.QDRANT_URL
qdrant_api_key = Config.QDRANT_API_KEY
# Seting up openai keys
openai_key = Config.OPENAI_API_KEY

# Initialize Qdrant client
client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=60)
# collection name
qdrant_collection_name = 'grade10_11'
vector_store = QdrantVectorStore(client=client, collection_name=qdrant_collection_name)
#create a vector index from the vector store
index = VectorStoreIndex.from_vector_store(vector_store)

# configure retriever
retriever = VectorIndexRetriever(
    index=index,
    similarity_top_k=5,
)

# configure response synthesizer
llm = OpenAI(
            model="gpt-4o",
            api_key= openai_key
            )

# synthersizer
synthesizer  = get_response_synthesizer(
    llm=llm,
    response_mode="compact", #refine
)

# Custom query engine
class RAGStringQueryEngine(CustomQueryEngine):
    """RAG String Query Engine."""

    retriever: BaseRetriever
    response_synthesizer: BaseSynthesizer
    llm: OpenAI
    qa_prompt: PromptTemplate

    def custom_query(self, query_str: str):
        nodes = self.retriever.retrieve(query_str)

        context_str = "\n\n".join([n.node.get_content() for n in nodes])
        response = self.llm.complete(
            qa_prompt.format(context_str=context_str, query_str=query_str)
        )

        return str(response)

# assemble query engine
query_engine = RAGStringQueryEngine(
    retriever=retriever,
    response_synthesizer=synthesizer,
    llm=llm,
    qa_prompt=qa_prompt,
)

# chat agent
class ChatAgent():
    def __init__(self, prompt, **kwargs):
        super().__init__( **kwargs)
        self.prompt = prompt
        self.openai_api_key = Config.OPENAI_API_KEY
        self.response = self.generate_response()
    
    def generate_response(self):
        try:
            # Using OpenAI model for response
            llm = OpenAI(
                model="gpt-4o",
                api_key= self.openai_api_key
                )
            response = llm.complete(
                prompt=self.prompt,
                temperature=0,
                )
            return response.text if hasattr(response, 'text') else response.choices[0].text
        except Exception as e:
            logger.log_with_color('error',f"Error generating response: {e}")
            return "An error occurred while generating the response."
    
    def get_response(self):
        return self.response

class GetContextEvent(Event):
    def __init__(self, query, **kwargs):
        super().__init__(**kwargs)
        self.query = query
    
    def get_context(self):
        response = query_engine.query(self.query)
        return response

class RefineAnswerEvent(Event):
    def __init__(self, query, context, **kwargs):
        super().__init__(**kwargs)
        self.prompt = self.generate_prompt(query, context)
        self.agent = ChatAgent(self.prompt)
        self.response = self.agent.get_response()
    
    def generate_prompt(self, query, context):
        prompt = f'''You are a professional reporter that writes comprehensive detailed reports for a given query and and for given context. From the query and given context prepare a comprehensive and structured answer that satisfy the same query given.
        
        query : {query}
        context : {context}
        
        *Note : Context taken from a specialized vector database for the application. Therefore under no circumstance, DO NOT add any other context on your own.
        '''
        
        return prompt

class QuestionAnswerFlow(Workflow):
    def __init__(self, query, **kwargs):
        super().__init__( **kwargs)
        self.query = query
    
    @step
    async def get_query_step(self, ev:StartEvent) -> GetContextEvent:
        try:
            logger.info("Workflow initiated")
            return GetContextEvent(query=self.query)
        except Exception as e:
            logger.error(f"Workflow initiation failed : {str(e)}")
    
    @step
    async def get_context_step(self, ev:GetContextEvent) -> RefineAnswerEvent:
        try:
            logger.info("Getting Context intiated")
            context = ev.get_context()
            logger.info(f"Returned context : {context}")
            return RefineAnswerEvent(query=self.query, context=context)
        except Exception as e:
            logger.error(f"Getting context from vector database failed : {str(e)}")
    
    @step
    async def get_result_step(self, ev:RefineAnswerEvent) -> StopEvent:
        try:
            logger.info("Getting Final Results intiated")
            result = ev.response
            return StopEvent(result=result)
        except Exception as e:
            logger.error(f"Generating final results failed : {str(e)}")

async def process_get_answer(query:str) -> str:
    """Process the input question asynchronously."""
    try:
        # get question
        w = QuestionAnswerFlow(query=query, timeout=20, verbose=False)
        result = await w.run()
        return result
    except Exception as e:
        logger.log_with_color('error', f"Error getting results: {e}")
        return "An error occurred while generating a response."