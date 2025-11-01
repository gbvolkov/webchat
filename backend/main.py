def main():
    from chromadb import PersistentClient
    client = PersistentClient(path=".chroma")
    print(client.list_collections())
    col = client.get_collection("chat_messages")
    print(col.count())



if __name__ == "__main__":
    main()
