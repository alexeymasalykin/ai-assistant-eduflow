# Incident Response Runbook

## Contacts

| Role | Contact |
|------|---------|
| Security owner | [FILL: name, telegram, phone] |
| DevOps | [FILL: name, telegram, phone] |
| Hosting provider | [FILL: provider support URL] |

## Runbook

### 1. Block compromised user

```bash
docker exec eduflow_db psql -U postgres -d ai_assistant_eduflow \
  -c "INSERT INTO blocked_users (wappi_chat_id, reason) VALUES ('<CHAT_ID>', 'security incident')"
```

### 2. Rotate API keys

1. Generate new keys in OpenAI / Wappi / Bitrix24 dashboards
2. Update `.env` on production server
3. Restart: `docker compose -f docker-compose.prod.yml restart webhook mcp-server`
4. Verify health: `curl https://DOMAIN/health`

### 3. Rollback deploy

```bash
git log --oneline -5  # find last known good commit
git checkout <commit>
docker compose -f docker-compose.prod.yml up -d --build webhook
```

### 4. Database backup restore

```bash
# List backups
ls -la /backups/postgres/

# Restore
docker exec -i eduflow_db psql -U postgres -d ai_assistant_eduflow < /backups/postgres/BACKUP_FILE.sql
```

## Post-mortem template

After resolving, create `docs/incidents/YYYY-MM-DD-title.md`:

1. **What happened:** timeline of events
2. **Impact:** affected users, data exposed, duration
3. **Root cause:** what allowed this to happen
4. **Fix:** what was done to resolve
5. **Prevention:** what changes prevent recurrence
