# Database migrations

Install [dbmate](https://github.com/amacneil/dbmate), set `DATABASE_URL` from the repository `.env.example`, then apply migrations with:

```sh
dbmate up
```

After changing migrations, update the checked-in schema dump with:

```sh
dbmate dump
```

The schema dump convention is `db/schema.sql`.
