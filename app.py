from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = "cheie_secreta_cabinet"

conn = mysql.connector.connect(
    host="yamabiko.proxy.rlwy.net",
    user="root",
    password="bSvMNGfqXMKpNIgbvkmCWkeJJkwwRxAa",
    database="railway",
    port=38937
)

cursor = conn.cursor()
def reconnect_db():
    global conn, cursor

    try:
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=2)

        conn.ping(reconnect=True, attempts=3, delay=2)
        cursor = conn.cursor()

    except Exception:
        conn = mysql.connector.connect(
            host="yamabiko.proxy.rlwy.net",
            user="root",
            password="bSvMNGfqXMKpNIgbvkmCWkeJJkwwRxAa",
            database="railway",
            port=38937
        )
        cursor = conn.cursor()


@app.before_request
def before_request():
    reconnect_db()

@app.route("/login", methods=["GET", "POST"])
def login():
    mesaj = ""

    if request.method == "POST":
        username = request.form["username"]
        parola = request.form["parola"]

        cursor.execute(
            "SELECT * FROM utilizatori WHERE username=%s AND parola=%s",
            (username, parola)
        )

        user = cursor.fetchone()

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            session["rol"] = user[3]
            session["id_medic"] = user[4]
            session["id_pacient"] = user[5]
            return redirect("/")
        else:
            mesaj = "Username sau parolă greșită!"

    return render_template("login.html", mesaj=mesaj)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] == "medic":
        return redirect("/dashboard_medic")

    if session["rol"] == "pacient":
        return redirect("/dashboard_pacient")

    cursor.execute("SELECT COUNT(*) FROM pacienti")
    total_pacienti = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM medici")
    total_medici = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM programari")
    total_programari = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM programari WHERE status='programata'")
    programari_active = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM consultatii")
    total_consultatii = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM retete")
    total_retete = cursor.fetchone()[0]

    return render_template(
        "index.html",
        total_pacienti=total_pacienti,
        total_medici=total_medici,
        total_programari=total_programari,
        programari_active=programari_active,
        total_consultatii=total_consultatii,
        total_retete=total_retete
    )


@app.route("/dashboard_medic")
def dashboard_medic():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "medic":
        return redirect("/")

    id_medic = session["id_medic"]

    cursor.execute("""
        SELECT nume, prenume, specializare
        FROM medici
        WHERE id_medic = %s
    """, (id_medic,))
    medic = cursor.fetchone()

    cursor.execute("""
        SELECT zi_saptamana, ora_start, ora_final, pauza_start, pauza_final
        FROM programmedic
        WHERE id_medic = %s
    """, (id_medic,))
    orar = cursor.fetchall()

    cursor.execute("""
        SELECT pr.id_programare,
               p.nume, p.prenume,
               pr.data_programare,
               pr.ora,
               pr.status,
               c.id_consultatie
        FROM programari pr
        JOIN pacienti p ON pr.id_pacient = p.id_pacient
        LEFT JOIN consultatii c ON pr.id_programare = c.id_programare
        WHERE pr.id_medic = %s
        ORDER BY pr.data_programare, pr.ora
    """, (id_medic,))
    programari = cursor.fetchall()

    cursor.execute("""
        SELECT c.id_consultatie,
               p.nume, p.prenume,
               pr.data_programare,
               c.diagnostic,
               c.observatii
        FROM consultatii c
        JOIN programari pr ON c.id_programare = pr.id_programare
        JOIN pacienti p ON pr.id_pacient = p.id_pacient
        WHERE pr.id_medic = %s
        ORDER BY pr.data_programare DESC
    """, (id_medic,))
    consultatii = cursor.fetchall()

    return render_template(
        "dashboard_medic.html",
        medic=medic,
        orar=orar,
        programari=programari,
        consultatii=consultatii
    )


@app.route("/medic_adauga_consultatie/<int:id_programare>", methods=["POST"])
def medic_adauga_consultatie(id_programare):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "medic":
        return redirect("/")

    diagnostic = request.form["diagnostic"]
    observatii = request.form["observatii"]

    cursor.execute("""
        UPDATE programari
        SET status = 'finalizata'
        WHERE id_programare = %s AND id_medic = %s
    """, (id_programare, session["id_medic"]))

    cursor.execute("""
        INSERT INTO consultatii (id_programare, diagnostic, observatii)
        VALUES (%s, %s, %s)
    """, (id_programare, diagnostic, observatii))

    conn.commit()
    return redirect("/dashboard_medic")


@app.route("/medic_sterge_consultatie/<int:id_consultatie>")
def medic_sterge_consultatie(id_consultatie):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "medic":
        return redirect("/")

    cursor.execute("""
        DELETE c FROM consultatii c
        JOIN programari pr ON c.id_programare = pr.id_programare
        WHERE c.id_consultatie = %s AND pr.id_medic = %s
    """, (id_consultatie, session["id_medic"]))

    conn.commit()
    return redirect("/dashboard_medic")


@app.route("/dashboard_pacient")
def dashboard_pacient():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "pacient":
        return redirect("/")

    id_pacient = session["id_pacient"]

    cursor.execute("""
        SELECT nume, prenume, telefon, email
        FROM pacienti
        WHERE id_pacient = %s
    """, (id_pacient,))
    pacient = cursor.fetchone()

    cursor.execute("""
        SELECT pr.id_programare,
               m.nume,
               m.prenume,
               pr.data_programare,
               pr.ora,
               pr.status
        FROM programari pr
        JOIN medici m ON pr.id_medic = m.id_medic
        WHERE pr.id_pacient = %s
        ORDER BY pr.data_programare DESC
    """, (id_pacient,))
    programari = cursor.fetchall()

    cursor.execute("""
        SELECT c.id_consultatie,
               m.nume,
               m.prenume,
               pr.data_programare,
               c.diagnostic,
               c.observatii
        FROM consultatii c
        JOIN programari pr ON c.id_programare = pr.id_programare
        JOIN medici m ON pr.id_medic = m.id_medic
        WHERE pr.id_pacient = %s
        ORDER BY pr.data_programare DESC
    """, (id_pacient,))
    consultatii = cursor.fetchall()

    cursor.execute("""
        SELECT r.id_reteta,
               m.nume,
               m.prenume,
               c.diagnostic,
               r.medicamente,
               r.data_emitere
        FROM retete r
        JOIN consultatii c ON r.id_consultatie = c.id_consultatie
        JOIN programari pr ON c.id_programare = pr.id_programare
        JOIN medici m ON pr.id_medic = m.id_medic
        WHERE pr.id_pacient = %s
        ORDER BY r.data_emitere DESC
    """, (id_pacient,))
    retete = cursor.fetchall()

    return render_template(
        "dashboard_pacient.html",
        pacient=pacient,
        programari=programari,
        consultatii=consultatii,
        retete=retete
    )


@app.route("/pacienti")
def pacienti():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    reconnect_db()

    search = request.args.get("search")
    show_add = request.args.get("show_add")
    edit_id = request.args.get("edit_id")
    istoric_id = request.args.get("istoric_id")

    if search:
        value = f"%{search}%"
        cursor.execute("""
            SELECT id_pacient, nume, prenume, CNP, data_nasterii, telefon, email
            FROM pacienti
            WHERE nume LIKE %s OR prenume LIKE %s OR CNP LIKE %s
            ORDER BY id_pacient DESC
        """, (value, value, value))
    else:
        cursor.execute("""
            SELECT id_pacient, nume, prenume, CNP, data_nasterii, telefon, email
            FROM pacienti
            ORDER BY id_pacient DESC
        """)

    pacienti = cursor.fetchall()

    istoric_data = []

    if istoric_id:
        cursor.execute("""
            SELECT 
                DATE_FORMAT(pr.data_programare, '%d.%m.%Y') AS data,
                TIME_FORMAT(pr.ora, '%H:%i') AS ora,
                CONCAT('Dr. ', m.nume, ' ', m.prenume) AS medic,
                m.specializare,
                UPPER(pr.status) AS status,
                COALESCE(c.diagnostic, 'În așteptare') AS diagnostic,
                COALESCE(c.observatii, 'Fără observații') AS observatii
            FROM pacienti p
            JOIN programari pr ON p.id_pacient = pr.id_pacient
            JOIN medici m ON pr.id_medic = m.id_medic
            LEFT JOIN consultatii c ON pr.id_programare = c.id_programare
            WHERE p.id_pacient = %s
            ORDER BY pr.data_programare DESC, pr.ora DESC
        """, (istoric_id,))
        istoric_data = cursor.fetchall()

    return render_template(
        "pacienti.html",
        pacienti=pacienti,
        show_add=True if show_add else False,
        edit_id=int(edit_id) if edit_id else None,
        istoric_id=int(istoric_id) if istoric_id else None,
        istoric_data=istoric_data
    )

@app.route("/adauga", methods=["POST"])
def adauga():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    nume = request.form["nume"]
    prenume = request.form["prenume"]
    cnp = request.form["cnp"]
    if not cnp.isdigit() or len(cnp) != 13:
        return "CNP invalid! Trebuie să conțină exact 13 cifre."
    data_nasterii = request.form["data_nasterii"]
    telefon = request.form["telefon"]
    email = request.form["email"]

    cursor.execute("""
        INSERT INTO pacienti (nume, prenume, CNP, data_nasterii, telefon, email)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (nume, prenume, cnp, data_nasterii, telefon, email))

    conn.commit()
    return redirect("/pacienti")


@app.route("/sterge/<int:id>")
def sterge(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    cursor.execute("DELETE FROM pacienti WHERE id_pacient=%s", (id,))
    conn.commit()
    return redirect("/pacienti")


@app.route("/istoric/<int:id>")
def istoric(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    sql = """
        SELECT 
            DATE_FORMAT(pr.data_programare, '%d %b %Y') AS data,
            TIME_FORMAT(pr.ora, '%H:%i') AS ora,
            CONCAT(p.nume, ' ', p.prenume) AS pacient,
            CONCAT('Dr. ', m.nume, ' ', m.prenume) AS medic,
            m.specializare,
            UPPER(pr.status) AS status,
            COALESCE(c.diagnostic, '--- In asteptare ---') AS diagnostic,
            COALESCE(c.observatii, 'Fara observatii') AS observatii
        FROM pacienti p
        JOIN programari pr ON p.id_pacient = pr.id_pacient
        JOIN medici m ON pr.id_medic = m.id_medic
        LEFT JOIN consultatii c ON pr.id_programare = c.id_programare
        WHERE p.id_pacient = %s
        ORDER BY pr.data_programare DESC, pr.ora DESC
    """

    cursor.execute(sql, (id,))
    data = cursor.fetchall()

    return render_template("istoric.html", data=data)


@app.route("/actualizeaza_pacient/<int:id>", methods=["POST"])
def actualizeaza_pacient(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    nume = request.form["nume"]
    prenume = request.form["prenume"]
    cnp = request.form["cnp"]
    if not cnp.isdigit() or len(cnp) != 13:
        return "CNP invalid! Trebuie să conțină exact 13 cifre."
    data_nasterii = request.form["data_nasterii"]
    telefon = request.form["telefon"]
    email = request.form["email"]

    cursor.execute("""
        UPDATE pacienti
        SET nume=%s,
            prenume=%s,
            CNP=%s,
            data_nasterii=%s,
            telefon=%s,
            email=%s
        WHERE id_pacient=%s
    """, (nume, prenume, cnp, data_nasterii, telefon, email, id))

    conn.commit()
    return redirect("/pacienti")


@app.route("/programari")
def programari():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    reconnect_db()

    edit_id = request.args.get("edit_id")
    show_add = request.args.get("show_add")
    search = request.args.get("search")

    if search:
        value = f"%{search}%"

        cursor.execute("""
            SELECT p.id_programare,
                   pa.nume,
                   pa.prenume,
                   m.nume,
                   m.prenume,
                   p.data_programare,
                   p.ora,
                   p.status,
                   c.id_consultatie
            FROM programari p
            JOIN pacienti pa ON p.id_pacient = pa.id_pacient
            JOIN medici m ON p.id_medic = m.id_medic
            LEFT JOIN consultatii c ON p.id_programare = c.id_programare
            WHERE pa.nume LIKE %s
               OR pa.prenume LIKE %s
               OR m.nume LIKE %s
               OR m.prenume LIKE %s
               OR p.status LIKE %s
               OR p.data_programare LIKE %s
            ORDER BY p.data_programare DESC
        """, (value, value, value, value, value, value))

    else:
        cursor.execute("""
            SELECT p.id_programare,
                   pa.nume,
                   pa.prenume,
                   m.nume,
                   m.prenume,
                   p.data_programare,
                   p.ora,
                   p.status,
                   c.id_consultatie
            FROM programari p
            JOIN pacienti pa ON p.id_pacient = pa.id_pacient
            JOIN medici m ON p.id_medic = m.id_medic
            LEFT JOIN consultatii c ON p.id_programare = c.id_programare
            ORDER BY p.data_programare DESC
        """)

    programari = cursor.fetchall()

    cursor.execute("SELECT id_pacient, nume, prenume FROM pacienti")
    pacienti = cursor.fetchall()

    cursor.execute("SELECT id_medic, nume, prenume FROM medici")
    medici = cursor.fetchall()

    return render_template(
        "programari.html",
        programari=programari,
        pacienti=pacienti,
        medici=medici,
        edit_id=int(edit_id) if edit_id else None,
        show_add=True if show_add else False,
        search=search
    )


@app.route("/actualizeaza_programare/<int:id>", methods=["POST"])
def actualizeaza_programare(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    data_programare = request.form["data_programare"]
    ora = request.form["ora"]
    status = request.form["status"]

    cursor.execute("""
        UPDATE programari
        SET data_programare=%s,
            ora=%s,
            status=%s
        WHERE id_programare=%s
    """, (data_programare, ora, status, id))

    conn.commit()
    return redirect("/programari")


@app.route("/adauga_programare", methods=["POST"])
def adauga_programare():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    id_pacient = request.form["id_pacient"]
    id_medic = request.form["id_medic"]
    data = request.form["data_programare"]
    ora = request.form["ora"]
    status = request.form["status"]

    cursor.execute("""
        INSERT INTO programari (id_pacient, id_medic, data_programare, ora, status)
        VALUES (%s, %s, %s, %s, %s)
    """, (id_pacient, id_medic, data, ora, status))

    conn.commit()
    return redirect("/programari")


@app.route("/sterge_programare/<int:id>")
def sterge_programare(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    cursor.execute("DELETE FROM programari WHERE id_programare=%s", (id,))
    conn.commit()
    return redirect("/programari")


@app.route("/medici")
def medici():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    show_add = request.args.get("show_add")
    edit_id = request.args.get("edit_id")

    cursor.execute("""
        SELECT id_medic, nume, prenume, specializare, telefon, email
        FROM medici
    """)
    medici = cursor.fetchall()

    return render_template(
        "medici.html",
        medici=medici,
        show_add=True if show_add else False,
        edit_id=int(edit_id) if edit_id else None
    )


@app.route("/adauga_medic", methods=["POST"])
def adauga_medic():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    nume = request.form["nume"]
    prenume = request.form["prenume"]
    specializare = request.form["specializare"]
    telefon = request.form["telefon"]
    email = request.form["email"]

    cursor.execute("""
        INSERT INTO medici (nume, prenume, specializare, telefon, email)
        VALUES (%s, %s, %s, %s, %s)
    """, (nume, prenume, specializare, telefon, email))

    conn.commit()
    return redirect("/medici")


@app.route("/actualizeaza_medic/<int:id>", methods=["POST"])
def actualizeaza_medic(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    nume = request.form["nume"]
    prenume = request.form["prenume"]
    specializare = request.form["specializare"]
    telefon = request.form["telefon"]
    email = request.form["email"]

    cursor.execute("""
        UPDATE medici
        SET nume=%s,
            prenume=%s,
            specializare=%s,
            telefon=%s,
            email=%s
        WHERE id_medic=%s
    """, (nume, prenume, specializare, telefon, email, id))

    conn.commit()
    return redirect("/medici")


@app.route("/sterge_medic/<int:id>")
def sterge_medic(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    cursor.execute("DELETE FROM medici WHERE id_medic=%s", (id,))
    conn.commit()
    return redirect("/medici")


@app.route("/consultatii")
def consultatii():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    reconnect_db()

    show_add = request.args.get("show_add")
    edit_id = request.args.get("edit_id")
    consultatie_id = request.args.get("consultatie_id")
    search = request.args.get("search")

    if consultatie_id:
        cursor.execute("""
            SELECT c.id_consultatie,
                   p.nume, p.prenume,
                   m.nume, m.prenume,
                   pr.data_programare,
                   c.diagnostic,
                   c.observatii,
                   r.id_reteta
            FROM consultatii c
            JOIN programari pr ON c.id_programare = pr.id_programare
            JOIN pacienti p ON pr.id_pacient = p.id_pacient
            JOIN medici m ON pr.id_medic = m.id_medic
            LEFT JOIN retete r ON c.id_consultatie = r.id_consultatie
            WHERE c.id_consultatie = %s
        """, (consultatie_id,))

    elif search:
        value = f"%{search}%"

        cursor.execute("""
            SELECT c.id_consultatie,
                   p.nume, p.prenume,
                   m.nume, m.prenume,
                   pr.data_programare,
                   c.diagnostic,
                   c.observatii,
                   r.id_reteta
            FROM consultatii c
            JOIN programari pr ON c.id_programare = pr.id_programare
            JOIN pacienti p ON pr.id_pacient = p.id_pacient
            JOIN medici m ON pr.id_medic = m.id_medic
            LEFT JOIN retete r ON c.id_consultatie = r.id_consultatie
            WHERE p.nume LIKE %s
               OR p.prenume LIKE %s
               OR m.nume LIKE %s
               OR m.prenume LIKE %s
               OR c.diagnostic LIKE %s
               OR c.observatii LIKE %s
               OR pr.data_programare LIKE %s
            ORDER BY pr.data_programare DESC
        """, (value, value, value, value, value, value, value))

    else:
        cursor.execute("""
            SELECT c.id_consultatie,
                   p.nume, p.prenume,
                   m.nume, m.prenume,
                   pr.data_programare,
                   c.diagnostic,
                   c.observatii,
                   r.id_reteta
            FROM consultatii c
            JOIN programari pr ON c.id_programare = pr.id_programare
            JOIN pacienti p ON pr.id_pacient = p.id_pacient
            JOIN medici m ON pr.id_medic = m.id_medic
            LEFT JOIN retete r ON c.id_consultatie = r.id_consultatie
            ORDER BY pr.data_programare DESC
        """)

    consultatii = cursor.fetchall()

    cursor.execute("""
        SELECT pr.id_programare,
               p.nume, p.prenume,
               m.nume, m.prenume,
               pr.data_programare,
               pr.ora
        FROM programari pr
        JOIN pacienti p ON pr.id_pacient = p.id_pacient
        JOIN medici m ON pr.id_medic = m.id_medic
        WHERE pr.status != 'finalizata'
    """)

    programari = cursor.fetchall()

    return render_template(
        "consultatii.html",
        consultatii=consultatii,
        programari=programari,
        show_add=True if show_add else False,
        edit_id=int(edit_id) if edit_id else None,
        search=search
    )


@app.route("/adauga_consultatie", methods=["POST"])
def adauga_consultatie():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    id_programare = request.form["id_programare"]
    diagnostic = request.form["diagnostic"]
    observatii = request.form["observatii"]

    cursor.execute("""
        UPDATE programari
        SET status = 'finalizata'
        WHERE id_programare = %s
    """, (id_programare,))

    cursor.execute("""
        INSERT INTO consultatii (id_programare, diagnostic, observatii)
        VALUES (%s, %s, %s)
    """, (id_programare, diagnostic, observatii))

    conn.commit()
    return redirect("/consultatii")


@app.route("/sterge_consultatie/<int:id>")
def sterge_consultatie(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    cursor.execute("DELETE FROM consultatii WHERE id_consultatie=%s", (id,))
    conn.commit()
    return redirect("/consultatii")


@app.route("/actualizeaza_consultatie/<int:id>", methods=["POST"])
def actualizeaza_consultatie(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    diagnostic = request.form["diagnostic"]
    observatii = request.form["observatii"]

    cursor.execute("""
        UPDATE consultatii
        SET diagnostic=%s,
            observatii=%s
        WHERE id_consultatie=%s
    """, (diagnostic, observatii, id))

    conn.commit()
    return redirect("/consultatii")


@app.route("/retete")
def retete():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    show_add = request.args.get("show_add")
    edit_id = request.args.get("edit_id")
    reteta_id = request.args.get("reteta_id")
    id_consultatie_selectata = request.args.get("id_consultatie")
    search = request.args.get("search")

    if reteta_id:
        cursor.execute("""
            SELECT r.id_reteta,
                   p.nume, p.prenume,
                   m.nume, m.prenume,
                   c.diagnostic,
                   r.medicamente,
                   r.data_emitere
            FROM retete r
            JOIN consultatii c ON r.id_consultatie = c.id_consultatie
            JOIN programari pr ON c.id_programare = pr.id_programare
            JOIN pacienti p ON pr.id_pacient = p.id_pacient
            JOIN medici m ON pr.id_medic = m.id_medic
            WHERE r.id_reteta = %s
        """, (reteta_id,))
    else:
        cursor.execute("""
            SELECT r.id_reteta,
                   p.nume, p.prenume,
                   m.nume, m.prenume,
                   c.diagnostic,
                   r.medicamente,
                   r.data_emitere
            FROM retete r
            JOIN consultatii c ON r.id_consultatie = c.id_consultatie
            JOIN programari pr ON c.id_programare = pr.id_programare
            JOIN pacienti p ON pr.id_pacient = p.id_pacient
            JOIN medici m ON pr.id_medic = m.id_medic
            ORDER BY r.data_emitere DESC
        """)

    retete = cursor.fetchall()

    if search:
    value = f"%{search}%"
    cursor.execute("""
        SELECT r.id_reteta,
               p.nume, p.prenume,
               m.nume, m.prenume,
               c.diagnostic,
               r.medicamente,
               r.data_emitere
        FROM retete r
        JOIN consultatii c ON r.id_consultatie = c.id_consultatie
        JOIN programari pr ON c.id_programare = pr.id_programare
        JOIN pacienti p ON pr.id_pacient = p.id_pacient
        JOIN medici m ON pr.id_medic = m.id_medic
        WHERE p.nume LIKE %s
           OR p.prenume LIKE %s
           OR m.nume LIKE %s
           OR m.prenume LIKE %s
           OR c.diagnostic LIKE %s
           OR r.medicamente LIKE %s
           OR r.data_emitere LIKE %s
        ORDER BY r.data_emitere DESC
    """, (value, value, value, value, value, value, value))
else:
    cursor.execute("""
        SELECT r.id_reteta,
               p.nume, p.prenume,
               m.nume, m.prenume,
               c.diagnostic,
               r.medicamente,
               r.data_emitere
        FROM retete r
        JOIN consultatii c ON r.id_consultatie = c.id_consultatie
        JOIN programari pr ON c.id_programare = pr.id_programare
        JOIN pacienti p ON pr.id_pacient = p.id_pacient
        JOIN medici m ON pr.id_medic = m.id_medic
        ORDER BY r.data_emitere DESC
    """)
    consultatii = cursor.fetchall()

    return render_template(
        "retete.html",
        retete=retete,
        consultatii=consultatii,
        show_add=True if show_add else False,
        edit_id=int(edit_id) if edit_id else None,
        id_consultatie_selectata=id_consultatie_selectata,
        search=search
    )


@app.route("/adauga_reteta", methods=["POST"])
def adauga_reteta():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    id_consultatie = request.form["id_consultatie"]
    medicamente = request.form["medicamente"]
    data_emitere = request.form["data_emitere"]

    cursor.execute("""
        INSERT INTO retete (id_consultatie, medicamente, data_emitere)
        VALUES (%s, %s, %s)
    """, (id_consultatie, medicamente, data_emitere))

    conn.commit()
    return redirect("/retete")


@app.route("/actualizeaza_reteta/<int:id>", methods=["POST"])
def actualizeaza_reteta(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    medicamente = request.form["medicamente"]
    data_emitere = request.form["data_emitere"]

    cursor.execute("""
        UPDATE retete
        SET medicamente=%s,
            data_emitere=%s
        WHERE id_reteta=%s
    """, (medicamente, data_emitere, id))

    conn.commit()
    return redirect("/retete")


@app.route("/sterge_reteta/<int:id>")
def sterge_reteta(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    cursor.execute("DELETE FROM retete WHERE id_reteta=%s", (id,))
    conn.commit()
    return redirect("/retete")


@app.route("/stoc")
def stoc():
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    reconnect_db()

    filtru = request.args.get("filtru", "toate")
    show_edit = request.args.get("show_edit")
    produs_selectat = request.args.get("produs_selectat")
    search = request.args.get("search")

    # lista pentru dropdown / căutare modificare
    if search:
        value = f"%{search}%"
        cursor.execute("""
            SELECT id_stoc, denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii
            FROM stoc
            WHERE denumire LIKE %s OR categorie LIKE %s OR furnizor LIKE %s
            ORDER BY denumire
        """, (value, value, value))
    else:
        cursor.execute("""
            SELECT id_stoc, denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii
            FROM stoc
            ORDER BY denumire
        """)

    produse_editare = cursor.fetchall()

    produs_editat = None

    if produs_selectat:
        cursor.execute("""
            SELECT id_stoc, denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii
            FROM stoc
            WHERE id_stoc = %s
        """, (produs_selectat,))
        produs_editat = cursor.fetchone()

    # tabel principal cu filtre
    if filtru == "medicamente":
        cursor.execute("""
            SELECT id_stoc, denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii
            FROM stoc
            WHERE categorie = 'medicament'
            ORDER BY denumire
        """)

    elif filtru == "echipamente":
        cursor.execute("""
            SELECT id_stoc, denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii
            FROM stoc
            WHERE categorie = 'echipament'
            ORDER BY denumire
        """)

    elif filtru == "epuizat":
        cursor.execute("""
            SELECT id_stoc, denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii
            FROM stoc
            WHERE cantitate = 0
            ORDER BY denumire
        """)

    elif filtru == "redus":
        cursor.execute("""
            SELECT id_stoc, denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii
            FROM stoc
            WHERE cantitate > 0 AND cantitate <= 5
            ORDER BY denumire
        """)

    elif filtru == "disponibil":
        cursor.execute("""
            SELECT id_stoc, denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii
            FROM stoc
            WHERE cantitate > 0
            ORDER BY denumire
        """)

    else:
        cursor.execute("""
            SELECT id_stoc, denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii
            FROM stoc
            ORDER BY denumire
        """)

    produse = cursor.fetchall()

    return render_template(
        "stoc.html",
        produse=produse,
        produse_editare=produse_editare,
        produs_editat=produs_editat,
        filtru=filtru,
        show_edit=True if show_edit else False,
        search=search
    )

@app.route("/actualizeaza_stoc/<int:id>", methods=["POST"])
def actualizeaza_stoc(id):
    if "user_id" not in session:
        return redirect("/login")

    if session["rol"] != "admin":
        return redirect("/")

    reconnect_db()

    denumire = request.form["denumire"]
    categorie = request.form["categorie"]
    cantitate = request.form["cantitate"]
    unitate = request.form["unitate"]
    data_expirare = request.form["data_expirare"]
    furnizor = request.form["furnizor"]
    observatii = request.form["observatii"]

    if data_expirare == "":
        data_expirare = None

    cursor.execute("""
        UPDATE stoc
        SET denumire=%s,
            categorie=%s,
            cantitate=%s,
            unitate=%s,
            data_expirare=%s,
            furnizor=%s,
            observatii=%s
        WHERE id_stoc=%s
    """, (denumire, categorie, cantitate, unitate, data_expirare, furnizor, observatii, id))

    conn.commit()

    filtru = request.form.get("filtru", "toate")
    return redirect(f"/stoc?show_edit=1&filtru={filtru}")

if __name__ == "__main__":
    app.run(debug=True)
