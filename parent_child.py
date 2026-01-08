import json
from langchain_core.documents import Document
def parent_child(input_filename):
    with open(input_filename) as f:
        data = json.load(f)
    parent_docs=[]
    child_docs=[]
    for chapter in data:
        for section in chapter['sections']:
            parent_doc = Document(
                page_content=section['original_content'],
                metadata={
                    'section_id': section["section_id"],
                    'title': section["title"],
                    'chapter':chapter['chapter_name'],
                    'doc_type': "parent"
                }
            )
            parent_docs.append(parent_doc)
            for unit in section['atomic_units']:
                child_doc = Document(
                    page_content= unit['enriched_context'],
                    metadata={
                        'parent_section_id': unit['parent_section_id'],
                        'unit_type': unit['unit_type'],
                        'chunk_index': unit['chunk_index'],
                        'doc_type': "child"
                    }
                )
                child_docs.append(child_doc)
    print(f"✅ Successfully prepared data.")
    print(f"   - Parent Documents (Full Sections): {len(parent_docs)}")
    print(f"   - Child Documents (Searchable Units): {len(child_docs)}")
    return parent_docs, child_docs



if __name__ == "__main__":
    parents, children = parent_child("cpa_anchored.json")

    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    import os
    import shutil
    from huggingface_hub import snapshot_download
    from tqdm.notebook import tqdm

    CHROMA_PATH = "./chroma_db_store"
    MODEL_NAME = "BAAI/bge-m3"
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
    snapshot_download(repo_id=MODEL_NAME, repo_type='model')

    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True,
                       'show_progress_bar': True}
    )

    vector_db = Chroma.from_documents(
        embedding=embeddings,
        documents=children,
        persist_directory=CHROMA_PATH,
        collection_name='cpa_legal_index'

    )
    vector_db.persist()



