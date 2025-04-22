import kb_manager
import constants
kb = kb_manager.KnowledgeBaseManager(constants.DOCS_PATH, constants.VECTORSTORE_PATH)

print(kb.kb_path)