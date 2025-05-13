from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Connexion à la base SQLite
engine = create_engine("sqlite:///users.db")  # Remplace par le bon chemin
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# Inspecteur pour lister les tables
inspector = inspect(engine)
tables = inspector.get_table_names()

print("Tables disponibles dans la base :")
for table in tables:
    print(f"\n📄 Table : {table}")
    
    # Requête brute pour récupérer toutes les lignes
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table}"))
        rows = result.fetchall()
        columns = result.keys()  # noms des colonnes

        # Affichage formaté
        if rows:
            print(" | ".join(columns))
            print("-" * 50)
            for row in rows:
                print(" | ".join(str(value) for value in row))
        else:
            print("Aucune donnée trouvée dans cette table.")

session.close()

