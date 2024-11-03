from langchain.document_loaders import TextLoader  # Importing a loader for documents
from langchain.schema import Document
from config import database  # Import your DB fetch function
from elasticsearch import Elasticsearch, NotFoundError
import logging 
from dotenv import load_dotenv
import openai ,os
from transformers import pipeline

es = Elasticsearch("http://localhost:9200")

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class DocumentIndexer:
    def __init__(self):
        self.index_name = "documents"
        self.index = None

    def create_index(self):
        """Create an index in Elasticsearch and populate it with documents from the database."""
        # Fetch parsed documents from your database
        documents = self.fetch_documents_from_db()  # Implement this function to get documents

        logging.info("Fetched documents: %s", documents)

        # Create the index in Elasticsearch if it doesn't exist
        if not es.indices.exists(index=self.index_name):
            es.indices.create(index=self.index_name)
            logging.info("Created index: %s", self.index_name)

        # Convert documents to LangChain Document format
        langchain_docs = [Document(page_content=doc['content'], metadata=doc['metadata']) for doc in documents]

        if not langchain_docs:
            logging.warning("No documents to index.")
            return  # Exit early if there are no documents

        # Index documents in Elasticsearch
        for doc in langchain_docs:
            try:
                es.index(index=self.index_name, document={
                    "title": doc.metadata.get('title'),
                    "description": doc.metadata.get('description'),
                    "content": doc.page_content
                })
                logging.info("Indexed document: %s", doc.metadata.get('title'))
            except Exception as e:
                logging.error("Error indexing document %s: %s", doc.metadata.get('title'), str(e))

    def fetch_documents_from_db(self):
        """Fetch documents from the database. Implement this function based on your database schema."""
        # Example implementation (replace with actual database fetching logic)
        return [
            {
                'content': 'This is the content of document 1.',
                'metadata': {'title': 'Document 1', 'description': 'Description of document 1'}
            },
            {
                'content': 'This is the content of document 2.',
                'metadata': {'title': 'Document 2', 'description': 'Description of document 2'}
            }
        ]

    def process_query(self, query):
        """Process a user query to retrieve relevant documents and generate a response."""
        if not self.index:
            raise Exception("Index not created. Please create the index first.")

        # Retrieve relevant documents from the index based on the query
        relevant_docs = self.retrieve_documents(query)

        # Generate response using retrieved documents
        response = self.generate_response(relevant_docs, query)
        return response

    def retrieve_documents(self, query):
        """Retrieve relevant documents from Elasticsearch based on the query."""
        try:
            response = es.search(index=self.index_name, body={
                "query": {
                    "match": {
                        "content": query
                    }
                }
            })
            return response['hits']['hits']  # Returns the relevant documents
        except NotFoundError:
            logging.error("Index not found: %s", self.index_name)
            return []

    # def generate_response(self,relevant_docs, query):
    #     """Generate a response based on the context of the relevant documents."""
    #     if not relevant_docs:
    #         return "No relevant documents found."

    #     # Combine the content of the relevant documents
    #     context = " ".join([doc['_source']['content'] for doc in relevant_docs])
    #     prompt = f"Based on the following documents, answer the question: {query}\n\nContext: {context}\n\nAnswer:"

    #     try:
    #         # Call the OpenAI API to generate a response
    #             response = openai.ChatCompletion.create(
    #             model="gpt-3.5-turbo",  # You can use other models as well
    #             messages=[
    #                 {"role": "user", "content": prompt}
    #             ]
    #         )
    #         # Extract the generated response
    #             generated_text = response['choices'][0]['message']['content']
    #             return generated_text
    #     except Exception as e:
    #             return f"Error generating response: {str(e)}"
    # def generate_response(self, relevant_docs, query):
    #     """Generate a response based on the context of the relevant documents using a local model."""
    #     if not relevant_docs:
    #         return "No relevant documents found."

    #     # Combine the content of the relevant documents
    #     context = " ".join([doc['_source']['content'] for doc in relevant_docs])
    #     prompt = f"Based on the following documents, answer the question: {query}\n\nContext: {context}\n\nAnswer:"

    #     # Use a Hugging Face transformer model for generating the response
    #     try:
    #         generator = pipeline("text-generation", model="distilgpt2")  # or another Hugging Face model
    #         response = generator(prompt, max_length=150, do_sample=True)
    #         generated_text = response[0]['generated_text']
    #         return generated_text
    #     except Exception as e:
    #         return f"Error generating response: {str(e)}"

    # def generate_response(self, relevant_docs, query):
        """Generate a response based on the context of the relevant documents using a QA-focused model."""
        if not relevant_docs:
            return "No relevant documents found."

        # Prepare context and prompt
        context = " ".join([doc['_source']['content'] for doc in relevant_docs])
        if len(context) > 500:  # Adjust length if needed
            context = context[:500] + "..."
        
        print("$$$$$$$$$$$$$$$",context)

        prompt = f"Answer the question based on the information: {query}\n\nInformation: {context}\n\nAnswer:"

        # Use a Hugging Face transformer model for generating the response
        try:
            generator = pipeline("question-answering", model="distilbert-base-uncased-distilled-squad")
            response = generator(prompt, max_length=200, do_sample=False)
            print(response)
            generated_text = response[0]['generated_text']
            return generated_text.strip()
        except Exception as e:
            return f"Error generating response: {str(e)}"
    from transformers import pipeline

    def generate_response(self,relevant_docs, query):
        """Generate a response based on the context of the relevant documents using a QA-focused model."""
        if not relevant_docs:
            return "No relevant documents found."

        # Prepare context from relevant documents
        context = " ".join([doc['_source']['content'] for doc in relevant_docs])
        if len(context) > 500:  # Adjust length if needed
            context = context[:500] + "..."

        print("$$$$$$$$$$$$$$$", context)

        # Use the question-answering pipeline
        try:
            generator = pipeline("question-answering", model="distilbert-base-uncased-distilled-squad")
            
            # Here we separate the question and context
            response = generator(question=query, context=context)  # Pass question and context separately
            print(response)
            # Extract generated answer
            generated_text = response['answer']  # Change this line to match the response structure
            return generated_text.strip()
        except Exception as e:
            return f"Error generating response: {str(e)}"

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    indexer = DocumentIndexer()
    indexer.create_index()