FROM alpine:3.19
RUN apk add --no-cache postgresql16-client gzip
COPY backup/backup_cron /etc/crontabs/root
COPY backup/backup.sh /backup.sh
COPY scripts/backup_db.sh /scripts/backup_db.sh
RUN chmod +x /backup.sh /scripts/backup_db.sh
CMD ["crond", "-f", "-l", "2"]
