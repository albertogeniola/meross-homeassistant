CREATE TABLE "users" ( `email` TEXT NOT NULL, `userid` INTEGER PRIMARY KEY AUTOINCREMENT, `password` TEXT NOT NULL, `mqtt_key` TEXT );
CREATE TABLE "http_tokens" ( `token` TEXT NOT NULL, `userid` INTEGER NOT NULL, PRIMARY KEY(`token`) );
CREATE TABLE "devices" ( `mac` TEXT NOT NULL, `owner_userid` INTEGER, PRIMARY KEY(`mac`) );