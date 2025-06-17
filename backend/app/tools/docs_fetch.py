from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import pathlib, os
import logging

SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]
KEY    = pathlib.Path(__file__).parents[2] / "keys" / "lesson_importer_key.json"
logger = logging.getLogger(__name__)

def fetch_doc(doc_id: str):
    logger.info(f"[docs_fetch] Fetching document {doc_id} using key at {KEY}")
    try:
        creds = Credentials.from_service_account_file(KEY, scopes=SCOPES)
        service = build("docs", "v1", credentials=creds, cache_discovery=False)
        response = service.documents().get(documentId=doc_id).execute()
        logger.info(f"[docs_fetch] Successfully fetched document titled: {response.get('title', 'Untitled')}")
        return response
    except Exception as e:
        logger.exception("[docs_fetch] Exception in fetching document")
        return {}
