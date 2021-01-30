CREATE TABLE `users`( `email` TEXT NOT NULL PRIMARY KEY, `userid` INTEGER UNIQUE NOT NULL, `salt` TEXT NOT NULL, `password` TEXT NOT NULL, `mqtt_key` TEXT );
CREATE TABLE `http_tokens`( `token` TEXT NOT NULL, `userid` INTEGER NOT NULL, PRIMARY KEY(`token`) );
CREATE TABLE `devices`( `mac` TEXT NOT NULL, `owner_userid` INTEGER, PRIMARY KEY(`mac`) );
