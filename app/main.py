# main.py
'''
main.py will be the main engine to run the api, it will also warm up the cache. 
Load the fresh messages and pass on to question answering layer (QA) and return a structured ask response. 
'''

from fastapi import FastAPI, HTTPException, Query

from .models import AskResponse
from .message_store import store
from .qa_logic import answer_question


app = FastAPI(title="Aurora Member Messages QA API")


@app.on_event("startup")
def warm_up_cache() -> None:
    try:
        store.ensure_fresh()
    except HTTPException:
        pass


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/status")
def stats() -> dict:
    snapshot = store.get_snapshot()
    return {
        "total_messages_cached": len(snapshot["messages"]),
        "distinct_users": len(snapshot["messages_by_user"]),
        "cache_last_refreshed": store._last_refresh_ts,
    }


@app.get("/ask", response_model=AskResponse)
def ask(
    question: str = Query(..., description="Natural-language question about member messages"),
) -> AskResponse:
    try:
        store.ensure_fresh()
    except HTTPException:
        return AskResponse(
            answer=(
                "I could not load member messages from the upstream service, "
                "so I am unable to answer your question right now."
            )
        )

    snapshot = store.get_snapshot()
    answer = answer_question(question, snapshot)
    return AskResponse(answer=answer)


