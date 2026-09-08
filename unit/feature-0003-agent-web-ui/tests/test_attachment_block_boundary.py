"""첨부 다음에 배치된 설명/diff가 파일에 저장된 라이브 구조의 회귀 검증."""
import json

import app
import pytest
from routers import ai_tools
from shared.attachment_write import apply_assistant_attachment_blocks


def block(kind, body, fence='```'):
    header = {'source_attachment_id': 1} if kind == 'edit' else {'filename': 'review.sql'}
    return f'{fence}attachment-{kind}\n{json.dumps(header)}\n{body}\n{fence}'


@pytest.mark.parametrize('kind', ['edit', 'new'])
@pytest.mark.parametrize('ending', ['\n', '\r\n'])
def test_file_ends_before_following_explanation_and_diff(kind, ending):
    body = '-- 원본 주석\nSELECT 1;'
    following = '**다음 파일의 검토**\n\n```diff\n- SELECT *;\n+ SELECT id;\n```'
    answer = (block(kind, body) + '\n\n' + following + '\n\n' + block(kind, 'SELECT 2;')).replace('\n', ending)
    parsed = getattr(app, f'_parse_attachment_{kind}_blocks')(answer)
    assert [p['content'].replace('\r\n', '\n').rstrip('\r') for p in parsed] == [body, 'SELECT 2;']
    clean = getattr(app, f'_strip_attachment_{kind}_blocks')(answer, [{'id': 1}, {'id': 2}])
    assert clean.replace('\r\n', '\n') == following


@pytest.mark.parametrize('kind', ['edit', 'new'])
@pytest.mark.parametrize('wrapper', ['````', '~~~'])
def test_quoted_attachment_is_never_materialized(kind, wrapper):
    answer = f'{wrapper}markdown\n{block(kind, "EXAMPLE")}\n{wrapper}'
    assert getattr(app, f'_parse_attachment_{kind}_blocks')(answer) == []
    assert getattr(app, f'_strip_attachment_{kind}_blocks')(answer, []) == answer


@pytest.mark.parametrize('kind', ['edit', 'new'])
def test_long_outer_fence_preserves_bare_fences_and_attachment_examples(kind):
    body = '# 문서\n```\n본문\n```\n' + block('new', 'SELECT 9;') + '\n끝'
    answer = block(kind, body, '````') + '\n```sql\nSELECT 3;\n```'
    assert getattr(app, f'_parse_attachment_{kind}_blocks')(answer)[0]['content'] == body
    assert getattr(app, f'_strip_attachment_{kind}_blocks')(answer, [{'id': 1}]) == '```sql\nSELECT 3;\n```'


@pytest.mark.parametrize('kind', ['edit', 'new'])
def test_successful_file_only_answer_has_no_delivery_narration(kind, monkeypatch):
    body = '-- 보존할 주석\nSELECT 1;'
    answer = block(kind, body)
    saved = []
    def materialize(conn, **kwargs):
        parsed = getattr(app, f'_parse_attachment_{kind}_blocks')(kwargs['answer'])
        assert parsed[0]['content'] == body
        return [{'id': 1, 'original_filename': 'review.sql'}]
    monkeypatch.setattr(app, f'_materialize_assistant_attachment_{"edits" if kind == "edit" else "new"}', materialize)
    monkeypatch.setattr(app, f'_materialize_assistant_attachment_{"new" if kind == "edit" else "edits"}', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_update_assistant_message_content', lambda *args: saved.append(args[-1]) or True)
    result = apply_assistant_attachment_blocks(None, account={'id': 1}, conversation_id='test', message_id=2, answer=answer, ops=app)
    assert result['answer'] == '' and saved == ['']
    assert result['answer_persisted'] and result['undelivered'] == 0
    assert len(result['edited']) + len(result['created']) == 1


@pytest.mark.parametrize('persisted, expected', [(True, ''), (False, None)])
def test_bridge_distinguishes_empty_persisted_answer_from_failure(monkeypatch, persisted, expected):
    monkeypatch.setattr(app, '_apply_assistant_attachment_blocks', lambda *a, **kw: {'answer': '', 'answer_persisted': persisted})
    clean, _, _ = ai_tools._materialize_bridge_attachments(None, account={'id': 1}, conversation_id='test', message_id=2, answer='raw', task_id='test')
    assert clean == expected


def test_attachment_tag_prefix_is_not_a_write_instruction():
    assert app._parse_attachment_new_blocks('```attachment-new-example\n{}\nEXAMPLE\n```') == []


def test_attachment_prompt_explains_file_boundary_and_avoids_narration():
    import agent_core
    directive = agent_core._ATTACHMENT_DELIVERY_DIRECTIVE
    assert 'longer than every fence inside the file' in directive
    assert 'do not add delivery confirmations' in directive
    assert 'Preserve original comments' in directive


@pytest.mark.parametrize('inner', ['```sql', '~~~sql'])
def test_long_outer_close_wins_over_unclosed_inner_file_fence(inner):
    body = '# 문서\n' + inner + '\nSELECT 1;'
    following = '**다음 설명**\n```diff\n+ next\n```'
    answer = block('new', body, '````') + '\n' + following
    assert app._parse_attachment_new_blocks(answer)[0]['content'] == body
    assert app._strip_attachment_new_blocks(answer, [{'id': 1}]) == following


@pytest.mark.parametrize('prefix', ['    ', '\t'])
def test_indented_code_example_is_not_an_attachment(prefix):
    answer = '\n'.join(prefix + line for line in block('new', 'SELECT 1;').splitlines())
    assert app._parse_attachment_new_blocks(answer) == []
    assert app._strip_attachment_new_blocks(answer, []) == answer


def test_bridge_delivery_saves_empty_clean_answer_to_recall(monkeypatch):
    import agent_core
    from types import SimpleNamespace
    saved = []
    cursor = SimpleNamespace(execute=lambda *a: None, fetchone=lambda: ('test', 'web', 1, 'pinned', 'question'), close=lambda: None)
    conn = SimpleNamespace(cursor=lambda: cursor, commit=lambda: None)
    monkeypatch.setattr(agent_core, '_answer_product_attribution', lambda *a: {})
    monkeypatch.setattr(agent_core, '_save_message', lambda *a, **kw: saved.append(kw['content']))
    monkeypatch.setattr(ai_tools, '_bridge_task_duration_meta', lambda *a: {})
    monkeypatch.setattr(ai_tools, '_replace_bridge_placeholder', lambda *a: 2)
    monkeypatch.setattr(ai_tools, '_materialize_bridge_attachments', lambda *a, **kw: ('', [], [{'id': 1}]))
    monkeypatch.setattr(ai_tools, '_materialize_bridge_steps', lambda *a: 0)
    assert ai_tools._deliver_web_bridge_answer(conn, 'task', {'id': 1}, block('new', 'SELECT 1;'))
    assert saved == ['']
