USE master;
GO

-- Borrar base de datos si existe para empezar de cero
IF EXISTS (SELECT * FROM sys.databases WHERE name = 'SIGELFA')
    DROP DATABASE SIGELFA;
GO

CREATE DATABASE SIGELFA;
GO

USE SIGELFA;
GO

-- =============================================
-- 1. ESTRUCTURA BÁSICA (LIGA, TORNEO, CATEGORÍA)
-- =============================================
CREATE TABLE Liga (
    cveLiga VARCHAR(4) PRIMARY KEY,
    nombLiga VARCHAR(30)
);

CREATE TABLE Torneo (
    PerTorneo VARCHAR(5) NOT NULL,
    nombTorneo VARCHAR(30),
    cveLiga VARCHAR(4) NOT NULL,
    CONSTRAINT PK_Torneo PRIMARY KEY (PerTorneo, cveLiga),
    CONSTRAINT FK_Torneo_Liga FOREIGN KEY (cveLiga) REFERENCES Liga(cveLiga)
);

CREATE TABLE Categoria (
    nomCortoCat VARCHAR(4) NOT NULL,
    cveLiga VARCHAR(4) NOT NULL,
    perTorneo VARCHAR(5) NOT NULL,
    CONSTRAINT PK_Categoria PRIMARY KEY (nomCortoCat, perTorneo, cveLiga),
    CONSTRAINT FK_Categoria_Torneo FOREIGN KEY (perTorneo, cveLiga) REFERENCES Torneo(PerTorneo, cveLiga)
);

-- =============================================
-- 2. TABLA EQUIPO 
-- =============================================
CREATE TABLE Equipo (
    cveEquipo VARCHAR(10) PRIMARY KEY, 
    nombEquipo VARCHAR(30),
    nomCortoCat VARCHAR(4) NOT NULL,
    perTorneo VARCHAR(5) NOT NULL,
    cveLiga VARCHAR(4) NOT NULL,
    CONSTRAINT FK_Equipo_Categoria FOREIGN KEY (nomCortoCat, perTorneo, cveLiga) 
    REFERENCES Categoria(nomCortoCat, perTorneo, cveLiga)
);

CREATE NONCLUSTERED INDEX IX_Equipo_Nombre ON Equipo(nombEquipo);

-- =============================================
-- 3. TABLAS PARA ROLES Y TRANSACCIONES 
-- =============================================
CREATE TABLE Arbitro_Tabla (
    numArb VARCHAR(4) PRIMARY KEY,
    nomArb VARCHAR(20),
    apPatArb VARCHAR(20)
);

CREATE TABLE Jornada (
    numJornada INTEGER NOT NULL,
    numEqLocal VARCHAR(10), 
    numEqVisita VARCHAR(10),
    nomCortoCat VARCHAR(4) NOT NULL,
    perTorneo VARCHAR(5) NOT NULL,
    cveLiga VARCHAR(4) NOT NULL,
    CONSTRAINT PK_Jornada PRIMARY KEY (numJornada, numEqLocal, numEqVisita, nomCortoCat, perTorneo, cveLiga),
    CONSTRAINT FK_Jornada_Categoria FOREIGN KEY (nomCortoCat, perTorneo, cveLiga) REFERENCES Categoria(nomCortoCat, perTorneo, cveLiga)
);

CREATE TABLE UnDeportiva (
    cveUd VARCHAR(4) PRIMARY KEY, 
    nombUd VARCHAR(30)
);

CREATE TABLE Cancha (
    numCancha INTEGER NOT NULL,
    cveUd VARCHAR(4) NOT NULL,
    CONSTRAINT PK_Cancha PRIMARY KEY (numCancha, cveUd),
    CONSTRAINT FK_Cancha_UD FOREIGN KEY (cveUd) REFERENCES UnDeportiva(cveUd)
);

CREATE TABLE Partido (
    horaPart VARCHAR(5),
    fechaPart DATE,
    numJornada INTEGER NOT NULL,
    numEqLocal VARCHAR(10),
    numEqVisita VARCHAR(10),
    nomCortoCat VARCHAR(4) NOT NULL,
    perTorneo VARCHAR(5) NOT NULL,
    cveLiga VARCHAR(4) NOT NULL,
    numCancha INTEGER NOT NULL,
    cveUd VARCHAR(4) NOT NULL,
    numArb VARCHAR(4) NOT NULL,
    CONSTRAINT PK_Partido PRIMARY KEY (numJornada, numEqLocal, numEqVisita, nomCortoCat, perTorneo, cveLiga),
    CONSTRAINT FK_Partido_Jornada FOREIGN KEY (numJornada, numEqLocal, numEqVisita, nomCortoCat, perTorneo, cveLiga) REFERENCES Jornada(numJornada, numEqLocal, numEqVisita, nomCortoCat, perTorneo, cveLiga),
    CONSTRAINT FK_Partido_Arbitro FOREIGN KEY (numArb) REFERENCES Arbitro_Tabla(numArb),
    CONSTRAINT FK_Partido_Cancha FOREIGN KEY (numCancha, cveUd) REFERENCES Cancha(numCancha, cveUd)
);

CREATE TABLE Jugador (
    numJug VARCHAR(4) PRIMARY KEY, 
    nomJug VARCHAR(20)
);

CREATE TABLE Jug_Part (
    golesJug INTEGER,
    numJug VARCHAR(4) NOT NULL,
    numJornada INTEGER NOT NULL,
    numEqLocal VARCHAR(10),
    numEqVisita VARCHAR(10),
    nomCortoCat VARCHAR(4) NOT NULL,
    perTorneo VARCHAR(5) NOT NULL,
    cveLiga VARCHAR(4) NOT NULL,
    CONSTRAINT PK_Jug_Part PRIMARY KEY (numJug, numJornada, numEqLocal, numEqVisita, nomCortoCat, perTorneo, cveLiga),
    CONSTRAINT FK_JugPart_Jugador FOREIGN KEY (numJug) REFERENCES Jugador(numJug),
    CONSTRAINT FK_JugPart_Partido FOREIGN KEY (numJornada, numEqLocal, numEqVisita, nomCortoCat, perTorneo, cveLiga) REFERENCES Partido(numJornada, numEqLocal, numEqVisita, nomCortoCat, perTorneo, cveLiga)
);

-- =============================================
-- 4. TABLAS DE GERENCIA 
-- =============================================
CREATE TABLE Concepto (
    cveConc VARCHAR(3) PRIMARY KEY, 
    descConc VARCHAR(30), 
    cveLiga VARCHAR(4) NOT NULL,
    CONSTRAINT FK_Concepto_Liga FOREIGN KEY (cveLiga) REFERENCES Liga(cveLiga)
);

CREATE TABLE Movimiento (
    numMov INTEGER, 
    fechaMov DATE, 
    montoMov REAL, 
    cveConc VARCHAR(3) NOT NULL, 
    CONSTRAINT PK_Mov PRIMARY KEY (numMov, cveConc),
    CONSTRAINT FK_Mov_Conc FOREIGN KEY (cveConc) REFERENCES Concepto(cveConc)
);

-- =============================================
-- 5. SEGURIDAD APLICACIÓN WEB
-- =============================================
CREATE TABLE Usuario_App (
    idUsuario INT IDENTITY(1,1) PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_real VARCHAR(100),
    rol VARCHAR(20) CHECK (rol IN ('Admin', 'Arbitro', 'Usuario'))
);
GO

-- =============================================
-- 6. SEGURIDAD: ROLES Y USUARIOS NATIVOS DE SQL
-- =============================================
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'Gerente') CREATE ROLE Gerente;
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'Asistente') CREATE ROLE Asistente;
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'Arbitro') CREATE ROLE Arbitro;

GRANT SELECT, INSERT, UPDATE, DELETE ON Movimiento TO Gerente;
GRANT SELECT, INSERT ON Movimiento TO Asistente;

GRANT SELECT, INSERT, UPDATE, DELETE ON Jug_Part TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Partido TO Arbitro;
GRANT SELECT, INSERT, DELETE ON Jornada TO Arbitro;
GRANT SELECT ON Equipo TO Arbitro;
GRANT SELECT ON Cancha TO Arbitro;
GRANT SELECT ON UnDeportiva TO Arbitro;
GRANT SELECT ON Arbitro_Tabla TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Usuario_App TO Arbitro; 

IF EXISTS (SELECT * FROM sys.server_principals WHERE name = 'LoginArb1') DROP LOGIN LoginArb1;
CREATE LOGIN LoginArb1 WITH PASSWORD = 'ArbPassword123';
CREATE USER UserArb1 FOR LOGIN LoginArb1;
ALTER ROLE Arbitro ADD MEMBER UserArb1;
GO

SELECT * FROM Usuario_App;

GRANT SELECT, INSERT, UPDATE, DELETE ON Liga TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Torneo TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Categoria TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Equipo TO Arbitro;
GRANT INSERT, UPDATE, DELETE ON Arbitro_Tabla TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Jugador TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Concepto TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Movimiento TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON UnDeportiva TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Cancha TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Partido TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Jug_Part TO Arbitro;
GRANT SELECT, INSERT, UPDATE, DELETE ON Jug_Part TO Arbitro;


ALTER TABLE Jugador ADD apPatJug VARCHAR(20);
ALTER TABLE Jugador ADD apMatJug VARCHAR(20);
ALTER TABLE Jugador ADD fNacJug DATE;
ALTER TABLE Jugador ADD cveEquipo VARCHAR(10);

ALTER TABLE Jugador 
ADD CONSTRAINT FK_Jugador_Equipo 
FOREIGN KEY (cveEquipo) REFERENCES Equipo(cveEquipo);

SELECT TOP 1 * FROM Partido;

INSERT INTO Usuario_App (username, password_hash, nombre_real, rol)
VALUES ('aficionado', '123', 'Juan Pérez', 'Usuario');