from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.security import check_password_hash
import pyodbc
from datetime import date
from datetime import date, datetime



app = Flask(__name__)
# Esta clave es necesaria para mantener la sesión del usuario segura
app.secret_key = 'sigelfa_super_secreta_2024'

# Configuración de la base de datos
CONN_STR = (
    'Driver={ODBC Driver 17 for SQL Server};'
    'Server=DESKTOP-MDHMLTH;'
    'Database=SIGELFA;'
    'UID=sa;'
    'PWD=123456789;'
)

def get_db_connection():
    return pyodbc.connect(CONN_STR)

@app.route('/')
def index():
    # Si no hay sesión activa, lo mandamos al login
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    # Si ya inició sesión, le mostramos el menú principal según su rol
    return render_template('index.html', usuario=session['usuario'], rol=session['rol'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('username')
        pw_input = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Solo buscamos por nombre de usuario (sin la contraseña en el WHERE)
        cursor.execute("SELECT username, password_hash, rol, nombre_real FROM Usuario_App WHERE username=?", (user_input,))
        account = cursor.fetchone()
        conn.close()

        # 2. Si el usuario existe, verificamos el HASH de la contraseña
        if account and check_password_hash(account[1], pw_input):
            session['usuario'] = account[0]
            session['rol'] = account[2]
            session['nombre'] = account[3] # Esto es para el "Bienvenido {{ session['nombre'] }}"
            return redirect(url_for('index'))
        else:
            flash("Usuario o contraseña incorrectos", "error")
            
    return render_template('login.html')

@app.route('/ver_equipos')
def ver_equipos():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Consulta para traer equipos con sus jugadores y calcular edad
    query = """
    SELECT 
        E.nombEquipo,
        E.nomCortoCat,
        J.nomJug + ' ' + ISNULL(J.apPatJug, '') as nombreCompleto,
        DATEDIFF(YEAR, J.fNacJug, GETDATE()) as Edad,
        J.numJug
    FROM Equipo E
    LEFT JOIN Jugador J ON E.cveEquipo = J.cveEquipo
    ORDER BY E.nombEquipo, J.nomJug
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    
    # Organizamos los datos en un diccionario: { 'NombreEquipo': {'cat': 'LIB', 'jugadores': [...]} }
    equipos = {}
    for row in rows:
        nomb_e = row[0]
        if nomb_e not in equipos:
            equipos[nomb_e] = {'categoria': row[1], 'jugadores': []}
        if row[2]: # Si hay jugador
            equipos[nomb_e]['jugadores'].append({'nombre': row[2], 'edad': row[3], 'numero': row[4]})
    
    conn.close()
    return render_template('ver_equipos.html', equipos=equipos)

@app.route('/logout')
def logout():
    # Borramos la sesión y lo mandamos al login
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/equipos', methods=['GET', 'POST'])
def gestionar_equipos():
    # Proteger la ruta: Solo el Admin puede entrar aquí
    if 'usuario' not in session or session.get('rol') != 'Admin':
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        accion = request.form.get('accion')

        # === LÓGICA PARA CREAR LIGA, TORNEO Y CATEGORÍA ===
        if accion == 'crear_estructura':
            cveLiga = request.form['cveLiga'].upper()
            nombLiga = request.form['nombLiga']
            perTorneo = request.form['perTorneo'].upper()
            nombTorneo = request.form['nombTorneo']
            nomCortoCat = request.form['nomCortoCat'].upper()

            try:
                # Insertamos en cascada asegurándonos de no duplicar
                cursor.execute("IF NOT EXISTS (SELECT 1 FROM Liga WHERE cveLiga=?) INSERT INTO Liga (cveLiga, nombLiga) VALUES (?, ?)", (cveLiga, cveLiga, nombLiga))
                cursor.execute("IF NOT EXISTS (SELECT 1 FROM Torneo WHERE PerTorneo=? AND cveLiga=?) INSERT INTO Torneo (PerTorneo, nombTorneo, cveLiga) VALUES (?, ?, ?)", (perTorneo, cveLiga, perTorneo, nombTorneo, cveLiga))
                cursor.execute("IF NOT EXISTS (SELECT 1 FROM Categoria WHERE nomCortoCat=? AND perTorneo=? AND cveLiga=?) INSERT INTO Categoria (nomCortoCat, cveLiga, perTorneo) VALUES (?, ?, ?)", (nomCortoCat, perTorneo, cveLiga, nomCortoCat, cveLiga, perTorneo))
                conn.commit()
                flash('Estructura del torneo guardada correctamente.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error al crear estructura: {str(e)}', 'error')

        # === LÓGICA PARA REGISTRAR EQUIPOS ===
        elif accion == 'crear_equipo':
            cveEquipo = request.form['cveEquipo'].upper()
            nombEquipo = request.form['nombEquipo']
            
            # Recibimos las 3 llaves compuestas separadas por un "|"
            datos_cat = request.form.get('categoria_sel')
            
            if datos_cat:
                nomCortoCat, perTorneo, cveLiga = datos_cat.split('|')
                try:
                    cursor.execute("INSERT INTO Equipo (cveEquipo, nombEquipo, nomCortoCat, perTorneo, cveLiga) VALUES (?, ?, ?, ?, ?)", 
                                   (cveEquipo, nombEquipo, nomCortoCat, perTorneo, cveLiga))
                    conn.commit()
                    flash(f'Equipo {nombEquipo} registrado exitosamente.', 'success')
                except Exception as e:
                    conn.rollback()
                    flash(f'Error al registrar equipo: {str(e)}', 'error')
            else:
                flash('Debes seleccionar una categoría.', 'error')

    # Consultar datos para mostrarlos en la pantalla
    cursor.execute("SELECT nomCortoCat, perTorneo, cveLiga FROM Categoria")
    categorias = cursor.fetchall()

    cursor.execute("SELECT cveEquipo, nombEquipo, nomCortoCat, perTorneo FROM Equipo")
    equipos = cursor.fetchall()

    conn.close()
    return render_template('equipos.html', categorias=categorias, equipos=equipos)

def calcular_edad(fecha_nacimiento):
    if not fecha_nacimiento:
        return "N/A"
    
    # Si la base de datos nos entrega la fecha como texto, la convertimos a formato Fecha
    if isinstance(fecha_nacimiento, str):
        try:
            # Convierte el texto 'YYYY-MM-DD' a un objeto de fecha real
            fecha_nacimiento = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
        except ValueError:
            return "N/A"

    today = date.today()
    return today.year - fecha_nacimiento.year - ((today.month, today.day) < (fecha_nacimiento.month, fecha_nacimiento.day))

@app.route('/admin/jugadores', methods=['GET', 'POST'])
def gestionar_jugadores():
    if 'usuario' not in session or session.get('rol') != 'Admin':
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'crear':
            numJug = request.form['numJug'].upper()
            nomJug = request.form['nomJug']
            apPatJug = request.form['apPatJug']
            apMatJug = request.form['apMatJug']
            fNacJug = request.form['fNacJug']
            cveEquipo = request.form['cveEquipo']
            
            try:
                cursor.execute("""
                    INSERT INTO Jugador (numJug, nomJug, apPatJug, apMatJug, fNacJug, cveEquipo)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (numJug, nomJug, apPatJug, apMatJug, fNacJug, cveEquipo))
                conn.commit()
                flash('Jugador registrado exitosamente.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error al registrar jugador: {str(e)}', 'error')
        
        elif accion == 'eliminar':
            numJug_eliminar = request.form.get('numJug')
            cursor.execute("DELETE FROM Jugador WHERE numJug = ?", (numJug_eliminar,))
            conn.commit()
            flash('Jugador eliminado.', 'success')

    # Obtenemos equipos para el select
    cursor.execute("SELECT cveEquipo, nombEquipo FROM Equipo")
    equipos = cursor.fetchall()

    # Obtenemos jugadores para la tabla
    cursor.execute("SELECT numJug, nomJug, apPatJug, apMatJug, fNacJug, cveEquipo FROM Jugador")
    jugadores_raw = cursor.fetchall()
    
    # Procesamos los jugadores para incluir la edad calculada
    jugadores = []
    for j in jugadores_raw:
        edad = calcular_edad(j.fNacJug)
        # Manejamos los nulos por si el apellido materno está vacío
        nombre_completo = f"{j.nomJug} {j.apPatJug if j.apPatJug else ''} {j.apMatJug if j.apMatJug else ''}".strip()
        
        jugadores.append({
            'numJug': j.numJug,
            'nombre': nombre_completo,
            'edad': edad,
            'equipo': j.cveEquipo
        })

    conn.close()
    return render_template('jugadores.html', equipos=equipos, jugadores=jugadores)



@app.route('/admin/generar_jornadas', methods=['GET', 'POST'])
def generar_jornadas():
    if 'usuario' not in session or session.get('rol') != 'Admin':
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        datos_cat = request.form.get('categoria_sel')
        
        if datos_cat:
            nomCortoCat, perTorneo, cveLiga = datos_cat.split('|')
            
            # 1. Obtener todos los equipos de esta categoría
            cursor.execute("SELECT cveEquipo FROM Equipo WHERE nomCortoCat=? AND perTorneo=? AND cveLiga=?", 
                           (nomCortoCat, perTorneo, cveLiga))
            equipos = [row.cveEquipo for row in cursor.fetchall()]
            
            if len(equipos) < 2:
                flash('Se necesitan al menos 2 equipos para generar jornadas.', 'error')
            else:
                # 2. Verificar si ya existen jornadas para no duplicar
                cursor.execute("SELECT COUNT(*) FROM Jornada WHERE nomCortoCat=? AND perTorneo=? AND cveLiga=?", 
                               (nomCortoCat, perTorneo, cveLiga))
                if cursor.fetchone()[0] > 0:
                    flash('¡Las jornadas para este torneo ya fueron generadas previamente!', 'error')
                else:
                    # 3. ALGORITMO ROUND ROBIN (Todos contra todos)
                    # Si el número de equipos es impar, agregamos un equipo "Fantasma" para los descansos
                    if len(equipos) % 2 != 0:
                        equipos.append('DESCANSO')
                        
                    num_equipos = len(equipos)
                    total_jornadas = num_equipos - 1
                    partidos_por_jornada = num_equipos // 2
                    
                    try:
                        for i in range(total_jornadas):
                            num_jornada = i + 1
                            
                            for j in range(partidos_por_jornada):
                                local = equipos[j]
                                visita = equipos[num_equipos - 1 - j]
                                
                                # Solo insertamos si ninguno es el equipo "Fantasma" de descanso
                                if local != 'DESCANSO' and visita != 'DESCANSO':
                                    cursor.execute("""
                                        INSERT INTO Jornada (numJornada, numEqLocal, numEqVisita, nomCortoCat, perTorneo, cveLiga)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    """, (num_jornada, local, visita, nomCortoCat, perTorneo, cveLiga))
                            
                            # Rotar los equipos (el índice 0 se queda fijo, los demás giran)
                            equipos.insert(1, equipos.pop())
                            
                        conn.commit()
                        flash(f'¡Éxito! Se generaron {total_jornadas} jornadas correctamente.', 'success')
                    except Exception as e:
                        conn.rollback()
                        flash(f'Error de base de datos al generar jornadas: {str(e)}', 'error')
        else:
            flash('Selecciona una categoría válida.', 'error')

    # Consultar las categorías y las jornadas existentes para la vista
    cursor.execute("SELECT nomCortoCat, perTorneo, cveLiga FROM Categoria")
    categorias = cursor.fetchall()
    
    # Consultar el resumen de jornadas creadas
    cursor.execute("""
        SELECT numJornada, numEqLocal, numEqVisita, nomCortoCat 
        FROM Jornada 
        ORDER BY nomCortoCat, numJornada
    """)
    jornadas_db = cursor.fetchall()

    conn.close()
    return render_template('generar_jornadas.html', categorias=categorias, jornadas=jornadas_db)

@app.route('/admin/arbitros', methods=['GET', 'POST'])
def gestionar_arbitros():
    # Solo el Admin puede gestionar a los árbitros
    if 'usuario' not in session or session.get('rol') != 'Admin':
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        numArb = request.form['numArb'].upper()
        nomArb = request.form['nomArb']
        apPatArb = request.form['apPatArb']

        try:
            cursor.execute("""
                INSERT INTO Arbitro_Tabla (numArb, nomArb, apPatArb) 
                VALUES (?, ?, ?)
            """, (numArb, nomArb, apPatArb))
            conn.commit()
            flash(f'Árbitro {nomArb} {apPatArb} registrado correctamente.', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error al registrar árbitro: {str(e)}', 'error')

    # Consultamos los árbitros para mostrarlos en la tabla
    cursor.execute("SELECT numArb, nomArb, apPatArb FROM Arbitro_Tabla")
    arbitros = cursor.fetchall()

    conn.close()
    return render_template('arbitros.html', arbitros=arbitros)

@app.route('/admin/conceptos', methods=['GET', 'POST'])
def gestionar_conceptos():
    if 'usuario' not in session or session.get('rol') != 'Admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        if accion == 'crear':
            cveConc = request.form['cveConc'].upper()
            descConc = request.form['descConc']
            cveLiga = request.form['cveLiga']
            try:
                cursor.execute("INSERT INTO Concepto (cveConc, descConc, cveLiga) VALUES (?, ?, ?)", 
                               (cveConc, descConc, cveLiga))
                conn.commit()
                flash('Concepto financiero registrado.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error al registrar concepto: {str(e)}', 'error')
                
        elif accion == 'eliminar':
            cveConc_eliminar = request.form.get('cveConc')
            try:
                cursor.execute("DELETE FROM Concepto WHERE cveConc = ?", (cveConc_eliminar,))
                conn.commit()
                flash('Concepto eliminado.', 'success')
            except Exception as e:
                conn.rollback()
                flash('Error al eliminar (Verifica que no haya movimientos ligados a este concepto).', 'error')

    cursor.execute("SELECT cveLiga, nombLiga FROM Liga")
    ligas = cursor.fetchall()
    
    cursor.execute("SELECT cveConc, descConc, cveLiga FROM Concepto")
    conceptos = cursor.fetchall()
    
    conn.close()
    return render_template('conceptos.html', ligas=ligas, conceptos=conceptos)

@app.route('/admin/movimientos', methods=['GET', 'POST'])
def gestionar_movimientos():
    if 'usuario' not in session or session.get('rol') != 'Admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        if accion == 'crear':
            cveConc = request.form['cveConc']
            fechaMov = request.form['fechaMov']
            montoMov = request.form['montoMov']
            
            try:
                # Calculamos automáticamente el siguiente número de movimiento para ese concepto
                cursor.execute("SELECT ISNULL(MAX(numMov), 0) + 1 FROM Movimiento WHERE cveConc = ?", (cveConc,))
                siguiente_numMov = cursor.fetchone()[0]
                
                cursor.execute("""
                    INSERT INTO Movimiento (numMov, fechaMov, montoMov, cveConc) 
                    VALUES (?, ?, ?, ?)
                """, (siguiente_numMov, fechaMov, montoMov, cveConc))
                conn.commit()
                flash(f'Movimiento #{siguiente_numMov} guardado exitosamente.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error al guardar movimiento: {str(e)}', 'error')
                
        elif accion == 'eliminar':
            numMov = request.form.get('numMov')
            cveConc = request.form.get('cveConc')
            cursor.execute("DELETE FROM Movimiento WHERE numMov = ? AND cveConc = ?", (numMov, cveConc))
            conn.commit()
            flash('Movimiento eliminado.', 'success')

    cursor.execute("SELECT cveConc, descConc FROM Concepto")
    conceptos = cursor.fetchall()
    
    # Usamos un JOIN para traer el nombre del concepto además de su clave
    cursor.execute("""
        SELECT M.numMov, M.fechaMov, M.montoMov, M.cveConc, C.descConc 
        FROM Movimiento M 
        JOIN Concepto C ON M.cveConc = C.cveConc 
        ORDER BY M.fechaMov DESC, M.numMov DESC
    """)
    movimientos = cursor.fetchall()
    
    conn.close()
    return render_template('movimientos.html', conceptos=conceptos, movimientos=movimientos)

@app.route('/admin/sedes', methods=['GET', 'POST'])
def gestionar_sedes():
    if 'usuario' not in session or session.get('rol') != 'Admin':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        # Lógica para Unidades Deportivas
        if accion == 'crear_ud':
            cveUd = request.form['cveUd'].upper()
            nombUd = request.form['nombUd']
            try:
                cursor.execute("INSERT INTO UnDeportiva (cveUd, nombUd) VALUES (?, ?)", (cveUd, nombUd))
                conn.commit()
                flash('Unidad Deportiva registrada.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error: {str(e)}', 'error')
        
        # Lógica para Canchas
        elif accion == 'crear_cancha':
            numCancha = request.form['numCancha']
            cveUd_sel = request.form['cveUd_sel']
            try:
                cursor.execute("INSERT INTO Cancha (numCancha, cveUd) VALUES (?, ?)", (numCancha, cveUd_sel))
                conn.commit()
                flash(f'Cancha {numCancha} agregada a la unidad.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error: La cancha {numCancha} ya existe en esa unidad.', 'error')

        elif accion == 'eliminar_ud':
            cveUd_del = request.form.get('cveUd')
            cursor.execute("DELETE FROM UnDeportiva WHERE cveUd = ?", (cveUd_del,))
            conn.commit()
            flash('Unidad eliminada.', 'success')

    # Consultas para mostrar en la página
    cursor.execute("SELECT cveUd, nombUd FROM UnDeportiva")
    unidades = cursor.fetchall()
    
    cursor.execute("""
        SELECT C.numCancha, C.cveUd, U.nombUd 
        FROM Cancha C 
        JOIN UnDeportiva U ON C.cveUd = U.cveUd
    """)
    canchas = cursor.fetchall()
    
    conn.close()
    return render_template('sedes.html', unidades=unidades, canchas=canchas)

@app.route('/admin/programar_partidos', methods=['GET', 'POST'])
def programar_partidos():
    if 'usuario' not in session or session.get('rol') != 'Admin':
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Recibir datos del formulario de programación
        hora = request.form['horaPart']
        fecha = request.form['fechaPart']
        numJ = request.form['numJornada']
        local = request.form['numEqLocal']
        visita = request.form['numEqVisita']
        cat = request.form['nomCortoCat']
        torneo = request.form['perTorneo']
        liga = request.form['cveLiga']
        cancha_data = request.form['cancha_ud'].split('|') # "numCancha|cveUd"
        numArb = request.form['numArb']

        try:
            cursor.execute("""
                INSERT INTO Partido (horaPart, fechaPart, numJornada, numEqLocal, numEqVisita, 
                                   nomCortoCat, perTorneo, cveLiga, numCancha, cveUd, numArb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (hora, fecha, numJ, local, visita, cat, torneo, liga, cancha_data[0], cancha_data[1], numArb))
            conn.commit()
            flash('Partido programado con éxito.', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error al programar: {str(e)}', 'error')

    # 1. Obtener jornadas que AÚN NO tienen partido programado
    cursor.execute("""
        SELECT J.* FROM Jornada J
        LEFT JOIN Partido P ON J.numJornada = P.numJornada 
            AND J.numEqLocal = P.numEqLocal 
            AND J.nomCortoCat = P.nomCortoCat
        WHERE P.numJornada IS NULL
    """)
    jornadas_pendientes = cursor.fetchall()

    # 2. Obtener Árbitros
    cursor.execute("SELECT numArb, nomArb + ' ' + apPatArb AS nombre FROM Arbitro_Tabla")
    arbitros = cursor.fetchall()

    # 3. Obtener Canchas con nombre de Unidad
    cursor.execute("""
        SELECT C.numCancha, C.cveUd, U.nombUd 
        FROM Cancha C JOIN UnDeportiva U ON C.cveUd = U.cveUd
    """)
    canchas = cursor.fetchall()

    # 4. Obtener Partidos ya programados para mostrar
    cursor.execute("SELECT * FROM Partido")
    partidos_listo = cursor.fetchall()

    conn.close()
    return render_template('programar_partidos.html', 
                           jornadas=jornadas_pendientes, 
                           arbitros=arbitros, 
                           canchas=canchas, 
                           partidos=partidos_listo)


    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'guardar':
            numJ = request.form.get('numJornada')
            loc = request.form.get('numEqLocal')
            vis = request.form.get('numEqVisita')
            obs = request.form.get('observaciones') # Nueva captura de observaciones
            
            ids_jugadores = request.form.getlist('jugador_id[]')
            goles_jugadores = request.form.getlist('goles[]')
            tarjetas_jugadores = request.form.getlist('tarjetas[]') # Captura de tarjetas

            try:
                # 1. Limpiar registros previos
                cursor.execute("DELETE FROM Jug_Part WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?", (numJ, loc, vis))
                
                # 2. Insertar cada jugador con su estadística
                for i in range(len(ids_jugadores)):
                    id_jug = ids_jugadores[i]
                    goles = int(goles_jugadores[i])
                    tarjeta = tarjetas_jugadores[i] # 'Y' para amarilla, 'R' para roja, '0' para nada

                    # Nota: Si tu tabla Jug_Part no tiene columna para tarjetas u observaciones, 
                    # el sistema solo guardará los goles. Asegúrate de tener esas columnas o usarlas para lógica interna.
                    cursor.execute("""
                        INSERT INTO Jug_Part (numJornada, numEqLocal, numEqVisita, numJug, golesJug, nomCortoCat, perTorneo, cveLiga)
                        SELECT ?, ?, ?, ?, ?, nomCortoCat, perTorneo, cveLiga 
                        FROM Partido 
                        WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?
                    """, (numJ, loc, vis, id_jug, goles, numJ, loc, vis))
                
                conn.commit()
                flash('Cédula guardada correctamente.', 'success')
                return redirect(url_for('cedula_arbitral'))
            except Exception as e:
                conn.rollback()
                flash(f'Error: {str(e)}', 'error')

    # (El resto de las consultas SELECT se mantienen igual que en la versión anterior)
    cursor.execute("""
        SELECT P.*, E1.nombEquipo as Local, E2.nombEquipo as Visita,
        (SELECT COUNT(*) FROM Jug_Part JP WHERE JP.numJornada = P.numJornada AND JP.numEqLocal = P.numEqLocal AND JP.numEqVisita = P.numEqVisita) as Registros
        FROM Partido P
        JOIN Equipo E1 ON P.numEqLocal = E1.cveEquipo
        JOIN Equipo E2 ON P.numEqVisita = E2.cveEquipo
    """)
    partidos = cursor.fetchall()

    id_partido = request.args.get('id_partido')
    partido_sel, j_local, j_visita = None, [], []
    if id_partido:
        partes = id_partido.split('|')
        if len(partes) >= 3:
            cursor.execute("SELECT * FROM Partido WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?", (partes[0], partes[1], partes[2]))
            partido_sel = cursor.fetchone()
            cursor.execute("SELECT numJug, nomJug + ' ' + apPatJug as nombre FROM Jugador WHERE cveEquipo = ?", (partes[1],))
            j_local = cursor.fetchall()
            cursor.execute("SELECT numJug, nomJug + ' ' + apPatJug as nombre FROM Jugador WHERE cveEquipo = ?", (partes[2],))
            j_visita = cursor.fetchall()

    conn.close()
    return render_template('cedula.html', partidos=partidos, partido_sel=partido_sel, j_local=j_local, j_visita=j_visita)


    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        accion = request.form.get('accion')
        
        # --- LÓGICA PARA GUARDAR ---
        if accion == 'guardar':
            numJ = request.form.get('numJornada')
            loc = request.form.get('numEqLocal')
            vis = request.form.get('numEqVisita')
            
            ids_jugadores = request.form.getlist('jugador_id[]')
            goles_jugadores = request.form.getlist('goles[]')
            # Las tarjetas y observaciones se reciben pero se guardarán si tienes las columnas en tu DB
            
            try:
                # Limpiar para no duplicar
                cursor.execute("DELETE FROM Jug_Part WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?", (numJ, loc, vis))
                
                for i in range(len(ids_jugadores)):
                    if int(goles_jugadores[i]) >= 0:
                        cursor.execute("""
                            INSERT INTO Jug_Part (numJornada, numEqLocal, numEqVisita, numJug, golesJug, nomCortoCat, perTorneo, cveLiga)
                            SELECT ?, ?, ?, ?, ?, nomCortoCat, perTorneo, cveLiga 
                            FROM Partido 
                            WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?
                        """, (numJ, loc, vis, ids_jugadores[i], goles_jugadores[i], numJ, loc, vis))
                
                conn.commit()
                flash('Cédula guardada.', 'success')
            except Exception as e:
                conn.rollback()
                print(f"Error al guardar: {e}")

        # --- LÓGICA PARA BORRAR (Sincronizada con el HTML) ---
        elif accion == 'eliminar':
            numJ = request.form.get('numJ')
            loc = request.form.get('loc')
            vis = request.form.get('vis')
            
            cursor.execute("DELETE FROM Jug_Part WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?", (numJ, loc, vis))
            conn.commit()
            return redirect(url_for('cedula_arbitral'))

    # Consulta para la tabla superior
    cursor.execute("""
        SELECT P.*, E1.nombEquipo as Local, E2.nombEquipo as Visita,
        (SELECT COUNT(*) FROM Jug_Part JP WHERE JP.numJornada = P.numJornada AND JP.numEqLocal = P.numEqLocal AND JP.numEqVisita = P.numEqVisita) as Registros
        FROM Partido P
        JOIN Equipo E1 ON P.numEqLocal = E1.cveEquipo
        JOIN Equipo E2 ON P.numEqVisita = E2.cveEquipo
    """)
    partidos = cursor.fetchall()

    # Selección de partido
    id_partido = request.args.get('id_partido')
    partido_sel, j_local, j_visita = None, [], []
    
    if id_partido:
        partes = id_partido.split('|')
        if len(partes) >= 3:
            cursor.execute("SELECT * FROM Partido WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?", (partes[0], partes[1], partes[2]))
            partido_sel = cursor.fetchone()
            cursor.execute("SELECT numJug, nomJug + ' ' + apPatJug as nombre FROM Jugador WHERE cveEquipo = ?", (partes[1],))
            j_local = cursor.fetchall()
            cursor.execute("SELECT numJug, nomJug + ' ' + apPatJug as nombre FROM Jugador WHERE cveEquipo = ?", (partes[2],))
            j_visita = cursor.fetchall()

    conn.close()
    return render_template('cedula.html', partidos=partidos, partido_sel=partido_sel, j_local=j_local, j_visita=j_visita)

@app.route('/arbitro/cedula', methods=['GET', 'POST'])
def cedula_arbitral():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'guardar':
            # Capturamos las llaves del partido
            numJ = request.form.get('numJornada')
            loc = request.form.get('numEqLocal')
            vis = request.form.get('numEqVisita')
            
            # Capturamos las listas de los inputs
            ids_jugadores = request.form.getlist('jugador_id[]')
            goles_jugadores = request.form.getlist('goles[]')

            try:
                # 1. Borramos lo anterior para evitar duplicados
                cursor.execute("DELETE FROM Jug_Part WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?", (numJ, loc, vis))
                
                # 2. Recorremos los jugadores enviados por el formulario
                for i in range(len(ids_jugadores)):
                    id_jug = ids_jugadores[i]
                    # Convertimos a entero, si está vacío ponemos 0
                    goles = int(goles_jugadores[i]) if goles_jugadores[i] else 0

                    # INSERTAMOS SIEMPRE (aunque sean 0 goles, para registrar que el jugador estuvo en la cédula)
                    # Usamos un SELECT interno para autocompletar nomCortoCat, perTorneo y cveLiga desde Partido
                    cursor.execute("""
                        INSERT INTO Jug_Part (numJornada, numEqLocal, numEqVisita, numJug, golesJug, nomCortoCat, perTorneo, cveLiga)
                        SELECT ?, ?, ?, ?, ?, nomCortoCat, perTorneo, cveLiga 
                        FROM Partido 
                        WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?
                    """, (numJ, loc, vis, id_jug, goles, numJ, loc, vis))
                
                conn.commit()
                print(f"✅ ÉXITO: Se procesaron {len(ids_jugadores)} jugadores para el partido {loc} vs {vis}")
                flash('Cédula guardada exitosamente', 'success')
            
            except Exception as e:
                conn.rollback()
                print(f"❌ ERROR AL GUARDAR: {e}")
                flash(f'Error al guardar: {str(e)}', 'error')

            return redirect(url_for('cedula_arbitral'))

        # Lógica para borrar
        elif accion == 'eliminar':
            numJ = request.form.get('numJ')
            loc = request.form.get('loc')
            vis = request.form.get('vis')
            cursor.execute("DELETE FROM Jug_Part WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?", (numJ, loc, vis))
            conn.commit()
            return redirect(url_for('cedula_arbitral'))

    # --- CONSULTAS PARA MOSTRAR LA PÁGINA ---
    cursor.execute("""
        SELECT P.*, E1.nombEquipo as Local, E2.nombEquipo as Visita,
        (SELECT COUNT(*) FROM Jug_Part JP WHERE JP.numJornada = P.numJornada AND JP.numEqLocal = P.numEqLocal AND JP.numEqVisita = P.numEqVisita) as Registros
        FROM Partido P
        JOIN Equipo E1 ON P.numEqLocal = E1.cveEquipo
        JOIN Equipo E2 ON P.numEqVisita = E2.cveEquipo
    """)
    partidos = cursor.fetchall()

    id_partido = request.args.get('id_partido')
    partido_sel, j_local, j_visita = None, [], []
    
    if id_partido:
        partes = id_partido.split('|')
        if len(partes) >= 3:
            cursor.execute("SELECT * FROM Partido WHERE numJornada=? AND numEqLocal=? AND numEqVisita=?", (partes[0], partes[1], partes[2]))
            partido_sel = cursor.fetchone()
            cursor.execute("SELECT numJug, nomJug + ' ' + apPatJug as nombre FROM Jugador WHERE cveEquipo = ?", (partes[1],))
            j_local = cursor.fetchall()
            cursor.execute("SELECT numJug, nomJug + ' ' + apPatJug as nombre FROM Jugador WHERE cveEquipo = ?", (partes[2],))
            j_visita = cursor.fetchall()

    conn.close()
    return render_template('cedula.html', partidos=partidos, partido_sel=partido_sel, j_local=j_local, j_visita=j_visita)

@app.route('/resultados')
def tabla_resultados():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Esta consulta suma los goles por partido y equipo para calcular puntos
    # Es una versión simplificada; lo ideal es tener una vista o procedimiento
    query = """
    SELECT 
        E.nombEquipo,
        COUNT(DISTINCT JP.numJornada) as JJ,
        SUM(JP.golesJug) as GF,
        -- Aquí podrías agregar lógica para calcular puntos (3, 1, 0)
        -- Por ahora mostraremos los datos básicos acumulados
        (SELECT COUNT(*) FROM Jug_Part WHERE golesJug > 0 AND numEqLocal = E.cveEquipo) as GolesTotales
    FROM Equipo E
    LEFT JOIN Jug_Part JP ON E.cveEquipo = JP.numEqLocal OR E.cveEquipo = JP.numEqVisita
    GROUP BY E.nombEquipo
    ORDER BY GolesTotales DESC
    """
    
    cursor.execute(query)
    resultados = cursor.fetchall()
    conn.close()
    
    return render_template('resultados.html', resultados=resultados)

@app.route('/jornadas')
def ver_jornadas():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Esta consulta trae los partidos y calcula la suma de goles para Local y Visita
    query = """
    SELECT 
        P.numJornada,
        E1.nombEquipo as Local,
        E2.nombEquipo as Visita,
        P.fechaPart,
        P.horaPart,
        -- Sumamos goles del Local
        ISNULL((SELECT SUM(golesJug) FROM Jug_Part JP 
                WHERE JP.numJornada = P.numJornada 
                AND JP.numEqLocal = P.numEqLocal 
                AND JP.numEqVisita = P.numEqVisita
                AND JP.numJug IN (SELECT numJug FROM Jugador WHERE cveEquipo = P.numEqLocal)), 0) as GolesLocal,
        -- Sumamos goles del Visita
        ISNULL((SELECT SUM(golesJug) FROM Jug_Part JP 
                WHERE JP.numJornada = P.numJornada 
                AND JP.numEqLocal = P.numEqLocal 
                AND JP.numEqVisita = P.numEqVisita
                AND JP.numJug IN (SELECT numJug FROM Jugador WHERE cveEquipo = P.numEqVisita)), 0) as GolesVisita,
        -- Verificamos si ya hay registros para saber si mostrar el marcador
        (SELECT COUNT(*) FROM Jug_Part JP 
         WHERE JP.numJornada = P.numJornada 
         AND JP.numEqLocal = P.numEqLocal 
         AND JP.numEqVisita = P.numEqVisita) as Jugado
    FROM Partido P
    JOIN Equipo E1 ON P.numEqLocal = E1.cveEquipo
    JOIN Equipo E2 ON P.numEqVisita = E2.cveEquipo
    ORDER BY P.numJornada ASC
    """
    
    cursor.execute(query)
    partidos = cursor.fetchall()
    conn.close()
    
    return render_template('jornadas.html', partidos=partidos)

@app.route('/jornadas_resultados')
def jornadas_resultados():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Nueva consulta: Sumamos goles uniendo Jug_Part con Jugador para saber el equipo
    query = """
    SELECT 
        P.numJornada,
        E1.nombEquipo as Local,
        E2.nombEquipo as Visita,
        P.fechaPart,
        -- Suma goles donde el jugador pertenece al equipo Local
        ISNULL((SELECT SUM(JP.golesJug) 
                FROM Jug_Part JP 
                JOIN Jugador J ON JP.numJug = J.numJug 
                WHERE JP.numJornada = P.numJornada 
                AND JP.numEqLocal = P.numEqLocal 
                AND J.cveEquipo = P.numEqLocal), 0) as GolesL,
        -- Suma goles donde el jugador pertenece al equipo Visita
        ISNULL((SELECT SUM(JP.golesJug) 
                FROM Jug_Part JP 
                JOIN Jugador J ON JP.numJug = J.numJug 
                WHERE JP.numJornada = P.numJornada 
                AND JP.numEqLocal = P.numEqLocal 
                AND J.cveEquipo = P.numEqVisita), 0) as GolesV,
        -- Verificador de si existe la cédula
        (SELECT COUNT(*) FROM Jug_Part WHERE numJornada = P.numJornada AND numEqLocal = P.numEqLocal) as Jugado
    FROM Partido P
    JOIN Equipo E1 ON P.numEqLocal = E1.cveEquipo
    JOIN Equipo E2 ON P.numEqVisita = E2.cveEquipo
    ORDER BY P.numJornada ASC
    """
    
    try:
        cursor.execute(query)
        partidos = cursor.fetchall()
    except Exception as e:
        print(f"Error en SQL: {e}")
        partidos = []
    finally:
        conn.close()
    
    return render_template('jornadas_resultados.html', partidos=partidos)

@app.route('/calendario_publico')
def calendario_publico():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Mostrar calendario de partidos y jornada
    query = """
SELECT 
    P.numJornada,
    E1.nombEquipo as Local,
    E2.nombEquipo as Visita,
    P.fechaPart,
    P.horaPart,
    -- Aquí usamos los nombres reales de tu imagen
    P.cveUd + ' - Cancha: ' + CAST(P.numCancha AS VARCHAR) as sedeReal, 
    -- Suma de goles (mantenemos la lógica que ya te funcionó)
    ISNULL((SELECT SUM(golesJug) FROM Jug_Part JP JOIN Jugador J ON JP.numJug = J.numJug 
            WHERE JP.numJornada = P.numJornada AND JP.numEqLocal = P.numEqLocal AND J.cveEquipo = P.numEqLocal), 0) as GolesL,
    ISNULL((SELECT SUM(golesJug) FROM Jug_Part JP JOIN Jugador J ON JP.numJug = J.numJug 
            WHERE JP.numJornada = P.numJornada AND JP.numEqLocal = P.numEqLocal AND J.cveEquipo = P.numEqVisita), 0) as GolesV,
    (SELECT COUNT(*) FROM Jug_Part WHERE numJornada = P.numJornada AND numEqLocal = P.numEqLocal) as Jugado
FROM Partido P
JOIN Equipo E1 ON P.numEqLocal = E1.cveEquipo
JOIN Equipo E2 ON P.numEqVisita = E2.cveEquipo
ORDER BY P.numJornada ASC
"""
    cursor.execute(query)
    partidos = cursor.fetchall()
    conn.close()
    return render_template('calendario_publico.html', partidos=partidos)

@app.route('/admin/reset_database', methods=['POST'])
def reset_database():
    # Seguridad: Solo el Admin puede ejecutar esto
    if 'usuario' not in session or session.get('rol') != 'Admin':
        flash("Acceso denegado.")
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # El orden de borrado es vital para no romper las restricciones de integridad
        # Borramos de lo más específico a lo más general
        cursor.execute("DELETE FROM Jug_Part")
        cursor.execute("DELETE FROM Movimiento")
        cursor.execute("DELETE FROM Partido")
        cursor.execute("DELETE FROM Jornada")
        cursor.execute("DELETE FROM Jugador")
        cursor.execute("DELETE FROM Equipo")
        cursor.execute("DELETE FROM Cancha")
        cursor.execute("DELETE FROM UnDeportiva")
        cursor.execute("DELETE FROM Categoria")
        cursor.execute("DELETE FROM Torneo")
        cursor.execute("DELETE FROM Concepto")
        cursor.execute("DELETE FROM Liga")
        
        
        conn.commit()
        flash("SISTEMA REINICIADO: Se han borrado todos los datos de la liga correctamente.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al reiniciar base de datos: {str(e)}", "error")
    finally:
        conn.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    # debug=True hace que el servidor se reinicie solo si haces cambios en el código
    app.run(debug=True)