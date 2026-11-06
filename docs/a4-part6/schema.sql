-- A4 Part 6. Create user_credentials first; foreign keys must be enabled.

PRAGMA foreign_keys = ON;

CREATE TABLE participation_history (
	sequence INTEGER NOT NULL, 
	id VARCHAR(100) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	service_id BIGINT NOT NULL, 
	service_name VARCHAR(100) NOT NULL, 
	joined_at BIGINT NOT NULL, 
	completed_at BIGINT, 
	outcome VARCHAR(10) NOT NULL, 
	position BIGINT NOT NULL, 
	close_notified BOOLEAN NOT NULL, 
	next_notified BOOLEAN NOT NULL, 
	queue_open BOOLEAN NOT NULL, 
	CONSTRAINT pk_participation_history PRIMARY KEY (sequence), 
	CONSTRAINT ck_participation_history_id_length CHECK (length(id) BETWEEN 1 AND 100), 
	CONSTRAINT ck_participation_history_service_name_length CHECK (length(service_name) BETWEEN 1 AND 100), 
	CONSTRAINT ck_participation_history_positive_numbers CHECK (service_id > 0 AND position > 0), 
	CONSTRAINT ck_participation_history_join_time_valid CHECK (joined_at >= 0), 
	CONSTRAINT ck_participation_history_outcome_valid CHECK (outcome IN ('Waiting', 'Served', 'Left queue', 'Removed')), 
	CONSTRAINT ck_participation_history_completion_valid CHECK ((outcome = 'Waiting' AND completed_at IS NULL) OR (outcome <> 'Waiting' AND completed_at >= joined_at AND completed_at IS NOT NULL)), 
	CONSTRAINT ck_participation_history_flags_valid CHECK (close_notified IN (0, 1) AND next_notified IN (0, 1) AND queue_open IN (0, 1)), 
	CONSTRAINT uq_participation_history_id UNIQUE (id), 
	CONSTRAINT fk_participation_history_user_id_user_credentials FOREIGN KEY(user_id) REFERENCES user_credentials (id) ON DELETE CASCADE
);

CREATE INDEX ix_participation_history_user_id ON participation_history (user_id);

CREATE TABLE notification (
	sequence INTEGER NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	recipient_id VARCHAR(36) NOT NULL, 
	participation_id VARCHAR(100) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	message VARCHAR(1000) NOT NULL, 
	type VARCHAR(10) NOT NULL, 
	timestamp BIGINT NOT NULL, 
	status VARCHAR(6) NOT NULL, 
	CONSTRAINT pk_notification PRIMARY KEY (sequence), 
	CONSTRAINT ck_notification_id_length CHECK (length(id) BETWEEN 1 AND 36), 
	CONSTRAINT ck_notification_message_length CHECK (length(message) BETWEEN 1 AND 1000), 
	CONSTRAINT ck_notification_kind_length CHECK (length(kind) BETWEEN 1 AND 40), 
	CONSTRAINT ck_notification_role_valid CHECK (role IN ('student', 'staff')), 
	CONSTRAINT ck_notification_type_valid CHECK (type IN ('success', 'warning', 'info', 'error')), 
	CONSTRAINT ck_notification_status_valid CHECK (status IN ('sent', 'viewed')), 
	CONSTRAINT ck_notification_timestamp_valid CHECK (timestamp >= 0), 
	CONSTRAINT uq_notification_id UNIQUE (id), 
	CONSTRAINT fk_notification_recipient_id_user_credentials FOREIGN KEY(recipient_id) REFERENCES user_credentials (id) ON DELETE CASCADE, 
	CONSTRAINT fk_notification_participation_id_participation_history FOREIGN KEY(participation_id) REFERENCES participation_history (id) ON DELETE CASCADE
);

CREATE INDEX ix_notification_recipient_id ON notification (recipient_id);
