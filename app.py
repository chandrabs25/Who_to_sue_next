


from dotenv import load_dotenv
load_dotenv()
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.graphs import Neo4jGraph
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
import streamlit as st

if "LANGCHAIN_API_KEY" in st.secrets:
    os.environ["LANGCHAIN_TRACING_V2"] = st.secrets["LANGCHAIN_TRACING_V2"]
    os.environ["LANGCHAIN_ENDPOINT"] = st.secrets["LANGCHAIN_ENDPOINT"]
    os.environ["LANGCHAIN_API_KEY"] = st.secrets["LANGCHAIN_API_KEY"]
    os.environ["LANGCHAIN_PROJECT"] = st.secrets["LANGCHAIN_PROJECT"]
st.title("WHO TO SUE NEXT")
@st.cache_resource
def resources():
    graph= Neo4jGraph(
        url=st.secrets["NEO4J_URI"],
        username=st.secrets["NEO4J_USERNAME"],
        password=st.secrets["NEO4J_PASSWORD"]
    )
    embeddings = HuggingFaceEndpointEmbeddings(model_name="BAAI/bge-m3",huggingfacehub_api_token=st.secrets["HF_TOKEN"],task="feature-extraction")
    llm = ChatGroq(model_name="moonshotai/kimi-k2-instruct-0905", temperature=0, api_key=st.secrets["GROQ_API_KEY"])
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


if "messages" not in st.session_state:
    st.session_state['messages'] = []

for message in st.session_state['messages']:
    with st.chat_message(message['role']):
        st.markdown(message['content'])
if prompt:=st.chat_input("Ask a question about Indian consumer protection law"):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:

            user_query_vector = embeddings.embed_query(prompt)
            result = graph.query(ret_query, params={'embedding': user_query_vector})
            if not result:
                print("No result from the graph")
                context = None
            else:
                context = result[0]['context']
                graph_context = llm_context(context)
            with st.sidebar:
                with st.expander("Retrieved Context from the Graph"):
                    st.text(graph_context)



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
            response = chain.invoke({'llm_query': graph_context, 'question': prompt})

            message_placeholder.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            st.error(e)




