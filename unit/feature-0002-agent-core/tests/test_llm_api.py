#!/usr/bin/env python3
"""Quick LLM API connectivity test."""
import os, time, json

def main():
    from openai import OpenAI
    key = (
        os.environ.get("BEDROCK_GATEWAY_API_KEY")
        or os.environ.get("LOCAL_LLM_API_KEY", "")
    )
    model = os.environ.get("OPENAI_MODEL", "claude-haiku-4")
    print(f"Model: {model}, Key present: {bool(key)}")
    c = OpenAI(api_key=key)
    start = time.time()
    # Test with a realistic plan payload
    plan_payload = json.dumps({
        "request": "건즈에서, 가장 많은 킬/어시스트 수를 달성한 클랜에 속해있는 상위 5개의 멤버들을 알려줄 수 있을지?",
        "mcp_tools": ["execute_sql", "search_objects"],
        "knowledge": {
            "insight_objects": [
                {"schema": "gunzlog", "table": "gameplayerlog", "summary": "게임 플레이어 로그. 킬(Kills), 데스(Deaths), 어시스트(Assists). 주요 컬럼: ID, CID, RegDate, Kills, Deaths, Assists, XP, BP"},
                {"schema": "gunzlog", "table": "killlog", "summary": "킬 로그"},
                {"schema": "have_00", "table": "clanjoin", "summary": "클랜 가입. 주요 컬럼: cl_id, cg_id"},
            ],
        },
    }, ensure_ascii=False)
    sys_prompt = "Return a JSON plan: {\"action\":\"step\",\"tool\":\"execute_sql\",\"args\":{\"sql\":\"...\"},\"intent\":\"...\"}"
    try:
        r = c.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": plan_payload},
            ],
            timeout=60,
        )
        elapsed = time.time() - start
        text = r.choices[0].message.content[:300] if r.choices else "NO_CHOICES"
        print(f"OK {elapsed:.1f}s: {text}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"ERR {elapsed:.1f}s: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
