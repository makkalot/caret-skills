# XCI Kanban API Reference

Base URL: `https://app.xci.ro/api/v1`

Authentication: `Authorization: Bearer <token>`

The source Swagger document is stored in `swagger.json`.

## Boards

- `GET /boards` - list boards available to the authenticated user.

## Columns

- `GET /boards/{boardID}/columns` - list board columns.

## Members

- `GET /boards/{boardID}/members` - list board members.

## Cards

- `GET /boards/{boardID}/cards` - list cards on a board.
- `GET /boards/{boardID}/cards?columnID={columnID}` - list cards in one column.
- `POST /boards/{boardID}/cards` - create a card.
- `GET /boards/{boardID}/cards/{cardID}` - get one card.
- `PUT /boards/{boardID}/cards/{cardID}` - update title, description, or assignee.
- `DELETE /boards/{boardID}/cards/{cardID}` - delete a card.
- `PATCH /boards/{boardID}/cards/{cardID}/status` - move a card to another column.

Create card body:

```json
{
  "title": "Fix login bug",
  "description": "The login form fails on submit",
  "column_id": 3,
  "assignee_id": 5,
  "tag_ids": [1, 2]
}
```

Update card body:

```json
{
  "title": "Updated title",
  "description": "Updated description",
  "assignee_id": 5
}
```

Move card body:

```json
{
  "column_id": 4
}
```

## Tags

- `GET /boards/{boardID}/tags` - list tags on a board.
- `POST /boards/{boardID}/tags` - create a tag.
- `PUT /boards/{boardID}/tags/{tagID}` - update tag name/color.
- `DELETE /boards/{boardID}/tags/{tagID}` - delete a tag.
- `POST /boards/{boardID}/cards/{cardID}/tags` - assign a tag to a card.
- `DELETE /boards/{boardID}/cards/{cardID}/tags/{tagID}` - remove a tag from a card.

Create/update tag body:

```json
{
  "name": "Bug",
  "color": "#ef4444"
}
```

Assign tag body:

```json
{
  "tag_id": 1
}
```
