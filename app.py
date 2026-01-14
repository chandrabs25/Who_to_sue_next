import os
import time
import sys
import sqlite3
if sqlite3.sqlite_version < "3.35":
    try:
        __import__('pysqlite3')
        sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
    except Exception:

        pass


from langchain_core.prompts import ChatPromptTemplate
from langchain_community.graphs import Neo4jGraph
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import Chroma
from langchain_classic.retrievers import EnsembleRetriever
from langchain_google_genai import ChatGoogleGenerativeAI

import streamlit as st
import pickle
import json
if "LANGCHAIN_API_KEY" in st.secrets:
    os.environ["LANGCHAIN_TRACING_V2"] = st.secrets["LANGCHAIN_TRACING_V2"]
    os.environ["LANGCHAIN_ENDPOINT"] = st.secrets["LANGCHAIN_ENDPOINT"]
    os.environ["LANGCHAIN_API_KEY"] = st.secrets["LANGCHAIN_API_KEY"]
    os.environ["LANGCHAIN_PROJECT"] = st.secrets["LANGCHAIN_PROJECT"]
    os.environ["LANGSMITH_TRACING"]= st.secrets["LANGSMITH_TRACING"]
    os.environ["LANGSMITH_ENDPOINT"] = st.secrets["LANGSMITH_ENDPOINT"]
    os.environ["LANGSMITH_API_KEY"] = st.secrets["LANGSMITH_API_KEY"]
    os.environ["GOOGLE_API_KEY"]= st.secrets["GOOGLE_API_KEY"]
st.title("WHO TO SUE NEXT")
@st.cache_resource
def get_vector_rag_resources():
    embeddings = HuggingFaceEndpointEmbeddings(model="BAAI/bge-m3", huggingfacehub_api_token=st.secrets["HF_TOKEN"],
                                               task="feature-extraction")
    vector_db = Chroma(persist_directory="./chroma_db_store_new",embedding_function=embeddings,collection_name='cpa_legal_index')
    chroma_retriever = vector_db.as_retriever(search_kwargs={"k": 5})
    with open('bm25_retriever.pkl', 'rb') as f:
        bm25_retriever = pickle.load(f)
    bm25_retriever.k = 5
    ensemble_retriever = EnsembleRetriever(retrievers=[bm25_retriever, chroma_retriever],weights=[0.5, 0.5])
    with open('cpa_anchored_refined_v2.json', 'r', encoding='UTF8') as f:
        data = json.load(f)
    parent_store = {}
    for chapter in data:
        for section in chapter['sections']:
            parent_store[section['section_id']] = section['original_content']
    vector_llm = ChatGoogleGenerativeAI(model='gemini-2.5-flash', temperature=0)
    return ensemble_retriever, vector_llm, parent_store
try:
    ensemble_retriever, vector_llm, parent_store = get_vector_rag_resources()
except Exception as e:
    st.error(e)

@st.cache_resource
def resources():
    graph= Neo4jGraph(
        url=st.secrets["NEO4J_URI"],
        username=st.secrets["NEO4J_USERNAME"],
        password=st.secrets["NEO4J_PASSWORD"]
    )
    embeddings = HuggingFaceEndpointEmbeddings(model="BAAI/bge-m3", huggingfacehub_api_token=st.secrets["HF_TOKEN"],
                                               task="feature-extraction")
    llm = ChatGoogleGenerativeAI(model='gemini-2.5-flash', temperature=0)
    return graph, embeddings, llm

try:
    graph, embeddings, groq_llm = resources()
except Exception as e:
    st.error(e)
    st.stop()

ret_query='''
CALL db.index.vector.queryNodes('section_embedding',5,$embedding)
YIELD node as s, score
WHERE score>0.7
WITH collect(
{ type: 'Section',
    title: s.title,
    text: s.text,
    score: score,
    id: s.id
}
) as section_results

CALL db.index.vector.queryNodes('concept_embedding',5,$embedding)
YIELD node as lc, score
WHERE score>0.7
MATCH (section2:Section)-[:DEFINES]->(lc)
WITH section_results, collect(
{ type: 'definition',

    term: lc.id,
    definition: lc.definition,

    score: score,
    source: section2.title}) as concept_results

UNWIND section_results as sec_res
MATCH (s:Section {id: sec_res.id})
OPTIONAL MATCH (s)-[:MENTIONS]->(entity)
WITH section_results, concept_results, sec_res, labels(entity) as tags, entity
WITH section_results, concept_results, sec_res, tags, entity,
CASE
    WHEN 'Authority' IN tags THEN 'Authority'
    WHEN 'Offense' IN tags THEN 'Offense'
    WHEN 'Penalty' IN tags THEN 'Penalty'
    WHEN 'Remedy' IN tags THEN 'Remedy'
    WHEN 'Stakeholder' IN tags THEN 'Stakeholder'
    ELSE head(tags) END AS label

WITH section_results, concept_results, sec_res, collect(DISTINCT entity.id + ' (' +label+ ')') as entities

WITH
collect({ type: 'Section',
    title: sec_res.title,
    text: sec_res.text,
    score: sec_res.score,
    mentions: entities
}) as updated_section, concept_results

RETURN {
sections: updated_section,
definitions: concept_results} as context

'''





def llm_context(context):
    llm_query=''
    if context:
        if context['definitions']:
            llm_query += 'Relevant Legal Definitions:\n'
            for item in context['definitions']:
                llm_query+=f'Term: {item["term"]}\n'
                llm_query += f'Source: {item["source"]}\n'
                llm_query += f'Definition: {item["definition"]}\n'

                llm_query += f'Score: {item["score"]}\n\n'
        if context['sections']:
            llm_query += 'Relevant Legal Sections:\n'
            for item in context['sections']:
                llm_query += f'Title: {item["title"]}\n'
                llm_query += f'Text: {item["text"]}\n'

                if item['mentions']:
                    mentions=[m for m in item['mentions']]
                    llm_query += f'Mentions: {", ".join(mentions)}\n'
        else:
            llm_query += 'Got no relevant legal context from the graph\n'
            return ''
    return llm_query

if "history" not in st.session_state:
    st.session_state["history"] = []
for history in st.session_state["history"]:
    with st.chat_message("User Question"):
        st.markdown(history['question'])

    col1, col2 = st.columns(2)
    with col1:
        st.info("HYBRID (Vector+BM25) RAG")
        st.markdown(history['hybrid_answer'])
        with st.expander("Context"):
            st.markdown(history['hybrid_context'])
    with col2:
        st.success("Graph RAG")
        st.markdown(history['graph_answer'])
        with st.expander("Context"):
            st.markdown(history['graph_context'])





if prompt:=st.chat_input("Ask a question about Indian consumer protection law"):
    st.chat_message("user").markdown(prompt)
    col1, col2 = st.columns(2)
    hybrid_answer=""
    hybrid_retrieved_context=""
    graph_answer=""
    graph_retrieved_context=""
    with col1:
        st.subheader("Vector BM25")
        status_vector_bm25 = st.status("Running hybrid (Vector+BM25) search", expanded=True)
        try:
            ensemble_retriever, vector_llm, parent_store= get_vector_rag_resources()
            status_vector_bm25.write("Retrieving relevant context")
            docs=ensemble_retriever.invoke(prompt)
            hybrid_context_list=[]
            seen_ids=set()
            for doc in docs:
                p_id=doc.metadata.get("parent_section_id")
                if p_id and p_id not in seen_ids:
                    hybrid_context_list.append(parent_store[p_id])
                    seen_ids.add(p_id)
            hybrid_context_test= "\n\n".join(hybrid_context_list)
            with st.expander("Read context"):
                st.markdown(hybrid_context_test)

            status_vector_bm25.write("Generating answer from the retrieved context")
            template = '''
            You are an expert Legal Assistant for Indian Consumer Law.
            Answer the user's question STRICTLY based on the provided context below.
            Rules:
            1. If the answer is not in the context, state "I cannot find the answer in the provided legal documents."
            2. Use the "Relevant Sections" to support your legal arguments.
            Context: {context}
    
            My question is {question}
            
            '''
            prompt_template = ChatPromptTemplate.from_template(template)
            chain = prompt_template | vector_llm | StrOutputParser()
            hybrid_answer=chain.invoke({"context": hybrid_context_test,"question": prompt})
            status_vector_bm25.update(label="Hybrid RAG(vector+bm25) complete", state="complete", expanded=False)
            st.markdown(hybrid_answer)


        except Exception as e:
            status_vector_bm25.write("An error occured")


    with col2:
        st.subheader("Graph RAG")
        status_graph_rag = st.status("Traversing the graph", expanded=True)

        try:
            graph, embeddings, groq_llm= resources()
            status_graph_rag.write("Querying Neo4j graph on vector embedding index")
            user_query_vector = embeddings.embed_query(prompt)
            result = graph.query(ret_query, params={'embedding': user_query_vector})
            if not result:
                context = None
            else:
                context = result[0]['context']
            graph_context_text = llm_context(context)
            if not graph_context_text:
                graph_context_text = "No relevant context from the graph was found"
            status_graph_rag.write("graph context retrieved")
            with st.expander("Read context while waiting(avoiding token limit/min"):
                st.markdown(graph_context_text)


            
            status_graph_rag.write(f"Generating the answer")

            system_prompt = """
            You are an expert Legal Assistant for Indian Consumer Law.
            Answer the user's question STRICTLY based on the provided context below.
    
            Rules:
            1. Use the "Relevant Definitions" to clarify terms.
            2. Use the "Relevant Sections" to support your legal arguments.
            3. Pay special attention to "Connected Entities" to understand who is responsible (e.g., Authorities vs Stakeholders).
            4. If the answer is not in the context, state "I cannot find the answer in the provided legal documents."
    
            Context:
            {llm_query}
            """
            prompt_template = ChatPromptTemplate.from_messages([('system', system_prompt), ('user', "{question}")])
            chain = prompt_template | groq_llm | StrOutputParser()
            response=''
            message_placeholder=st.empty()

            for chunk in chain.stream({'llm_query': graph_context_text, 'question': prompt}):
                response+=chunk
                message_placeholder.markdown(response)
            status_graph_rag.update(label="Graph RAG Complete!", state="complete", expanded=False)




        except Exception as e:
            st.error(e)

    st.session_state["history"].append({
        "question": prompt,
        "hybrid_answer": hybrid_answer,
        "hybrid_context": hybrid_context_test,
        "graph_answer": response,
        "graph_context": graph_context_text
    })




