# Modules and Files

## Modules

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/modules --all --param "include[]=items"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/modules \
    --json '{"module": {"name": "Week 5: Middleware", "position": 5}}' --live
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    put /courses/:course/modules/<id> \
    --json '{"module": {"published": true}}' --live
```

`include[]=items` truncates on very large modules; fetch
`/modules/<id>/items --all` when completeness matters.

Publishing a module does NOT publish its items; each item's underlying object
(assignment, page, quiz) has its own published state. An unpublished item
inside a published module is still invisible to students. Conversely,
unpublishing a module hides even published items. This is the usual answer to
"I published it and they still can't see it" (`gotchas.md` #5).

## Module items

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/modules/<mid>/items --json '{
  "module_item": {"title": "HW7", "type": "Assignment", "content_id": 222, "indent": 1}
}' --live
```

`type` values: `Assignment`, `Quiz`, `Page`, `Discussion`, `File`,
`SubHeader`, `ExternalUrl`, `ExternalTool`. Notes:
- `Page` items use `page_url` (the slug) instead of `content_id`.
- `ExternalUrl` needs `external_url` and benefits from `new_tab: true`.
- `SubHeader` is just a `title`, useful for visual grouping.
- Requirements (`completion_requirement`) and prerequisites
  (`prerequisite_module_ids` on the module) enable gated sequential flow.

## Files

Reading is easy; uploading is a three-step dance.

### Browse

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/folders --all
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    get /courses/:course/files --all --param search_term=syllabus
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 get /folders/<id>/files --all
```

### Upload (three steps)

```bash
# Step 1: tell Canvas about the file; it returns an upload target
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 \
    post /courses/:course/files --json '{
  "name": "hw7-handout.pdf",
  "size": 123456,
  "content_type": "application/pdf",
  "parent_folder_path": "handouts",
  "on_duplicate": "overwrite"
}' --live
# Response contains upload_url and upload_params.

# Step 2: POST the actual bytes as multipart form data to upload_url,
# including every key from upload_params BEFORE the file field. This target
# is usually external storage (S3/InstFS), so use curl, not canvas.py:
curl -s -F 'key=<from upload_params>' ... -F 'file=@hw7-handout.pdf' '<upload_url>'

# Step 3: follow the Location header / confirmation url from step 2's
# response (a GET with the Bearer token) to finalize. Some backends return
# the file JSON directly in step 2; if you get a file id, you are done.
```

The `upload_params` keys vary by storage backend; include exactly what Canvas
returned, in order, with the file field last. `on_duplicate` is `overwrite`
or `rename`.

Step 2 leaves `canvas.py`, which means it leaves the write gate and the
`actions.log` with it. Say so when you do it: an upload done this way is the
one write in this skill that has no audit line.

### File visibility

Files have their own locked/hidden/unlock_at states
(`PUT /files/<id>` with `locked`, `hidden`, `lock_at`, `unlock_at`). A file
linked from a published page but itself locked will 403 for students.

### Deleting

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/canvas.py --course 326 delete /files/<id> --live
```

Deleting a file breaks every page, module item, and link that references it.
List usages the user cares about and confirm first.
