from app.rag import retrieve_context

ctx = retrieve_context("learn devops")

for r in ctx:
    print(r.competency_name)

        #from auth import hash_password

#pwd = "Password@123"
#hashed = hash_password(pwd)

#print(hashed)