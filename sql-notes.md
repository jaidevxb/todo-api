# SQL notes — exploring tasks.db

Queries run directly against `tasks.db`, outside the API. Output below is what the
database actually returned.

## List every task

```sql
SELECT * FROM tasks;
```

```
(1, 'Buy milk', 0)
(2, 'Walk dog', 1)
(3, 'Write README', 0)
(4, 'Read SQL docs', 0)
(5, 'Buy bread', 0)
```

Ids 4 and 5 were created earlier through `POST /tasks` — the API and a SQL client are
looking at the same rows.

## Show only completed tasks

```sql
SELECT * FROM tasks WHERE done = 1;
```

```
(2, 'Walk dog', 1)
```

SQLite has no real boolean type, so `done` is stored as `0`/`1`. The API converts it
back to `true`/`false` in `to_task()`.

## Count all tasks

```sql
SELECT COUNT(*) FROM tasks;
```

```
(5,)
```

## Mark every task as completed

```sql
UPDATE tasks SET done = 1;
```

```
(5 rows affected)
```

No `WHERE` clause means *every* row is updated. Easy to do by accident.

## Delete all completed tasks

```sql
DELETE FROM tasks WHERE done = 1;
```

```
(5 rows affected)
```

Since the previous query had just marked everything as done, this emptied the table.

## Checkpoint — the API reflects manual SQL changes

With the table empty, restarting the server re-ran the seed step and inserted the three
example tasks again (`init_db()` only seeds when the table has no rows):

```
GET /tasks -> [{"id":1,"title":"Buy milk","done":false},
               {"id":2,"title":"Walk dog","done":true},
               {"id":3,"title":"Write README","done":false}]
```

Then, **with the server still running**, these statements were executed against the
database file directly:

```sql
UPDATE tasks SET title = 'Buy oat milk', done = 1 WHERE id = 1;
INSERT INTO tasks (title, done) VALUES ('Added by hand in SQL', 0);
```

`GET /tasks` immediately returned the change, with no restart:

```
[{"id":1,"title":"Buy oat milk","done":true},
 {"id":2,"title":"Walk dog","done":true},
 {"id":3,"title":"Write README","done":false},
 {"id":4,"title":"Added by hand in SQL","done":false}]
```

Each request opens its own connection and reads the current contents of the file, so
whatever is in `tasks.db` is what the API serves.
