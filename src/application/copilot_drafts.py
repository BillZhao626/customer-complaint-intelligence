"""Explicit insertion of an immutable suggestion into the reviewed draft flow."""
from src.application.product_workflow import Conflict
from src.domain.contracts import digest


def insert_suggestion(store, case_id, *, expected_revision, editor_text, expected_editor_hash,
                      mode, actor='demo_operator', actor_type='demo_test', operation_id=None):
    if digest(editor_text) != expected_editor_hash:
        raise Conflict('编辑器内容已变化，请重新选择插入方式')
    if mode not in ('replace', 'append'):
        raise Conflict('请选择替换或追加；不会静默覆盖已有草稿')
    case = store.get(case_id)
    if not case or not case['accepted'] or not case['draft']:
        raise Conflict('此邮件没有可信的可插入建议')
    suggestion = case['run'].result.suggested_reply
    body = editor_text.rstrip() + '\n\n' + suggestion if mode == 'append' and editor_text.strip() else suggestion
    return store.act(case_id, 'insert_suggestion', expected_revision=expected_revision,
        actor=actor, actor_type=actor_type, body=body,
        checks=dict(insertion_mode=mode, editor_base_hash=expected_editor_hash),
        reason='插入内部建议；必须重新人工审核', operation_id=operation_id)
