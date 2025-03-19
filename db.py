import sqlite3

# create table in the first run
conn = sqlite3.connect("context.db")
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS MUChatContext (
        ChatID TEXT PRIMARY KEY,
        PreviousContent TEXT NOT NULL
    )
    ''')
conn.commit()
conn.close()

class DatabaseManager:
    def __enter__(self):
        self.conn = sqlite3.connect("context.db")
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.close()
    
    def getDbChatId(self, content:str):
        self.cursor.execute("SELECT * FROM MUChatContext WHERE PreviousContent = ?", (content,))
        result = self.cursor.fetchone()
        if result is not None:
            chatId = result[0]
            return chatId
        else:
            return None

    def updateDbContext(self, chatId:str, content:str):
        self.cursor.execute("SELECT * FROM MUChatContext WHERE ChatID = ?", (chatId,))
        result = self.cursor.fetchone()
        # print(f"chatid: {chatId}, result: {result}")
        if result is not None:
            self.cursor.execute('''
                UPDATE MUChatContext SET PreviousContent = ? WHERE ChatID = ?
                ''', (content, chatId))
        else:
            self.cursor.execute('''
                INSERT INTO MUChatContext (ChatID, PreviousContent) VALUES (?, ?)
                ''', (chatId, content))
        self.conn.commit()