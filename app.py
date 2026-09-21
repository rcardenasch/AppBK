import models
# MODELOS
from models.socio import Socio
from models.accion import Accion
from models.prestamo import Prestamo
from models.movimiento import Movimiento
from models.periodo import Periodo
from models.fondo_utilidades import FondoUtilidades
from models.distribucion_utilidades import DistribucionUtilidades
from models.solicitud_prestamo import SolicitudPrestamo
from models.configuracion import Configuracion

# Seguridad
from models.usuario import Usuario
from models.rol import Rol
from models.permiso import Permiso
from models.rol_permiso import RolPermiso
from models.periodo import Periodo
from models.asistencia import Asistencia


from flask import Flask

from database.connection import SessionLocal
from routes.utilidades_routes import (utilidades_bp)
from routes.auth_routes import auth_bp
from routes.dashboard_routes import dashboard_bp
from routes.prestamos_routes import prestamos_bp
from routes.socios_routes import socios_bp
from routes.periodos_routes import periodos_bp
from routes.acciones_routes import acciones_bp
from routes.movimientos_routes import movimientos_bp
from routes.solicitudes_routes import solicitudes_bp
from routes.distribucion_routes import distribucion_bp
from routes.asistencias_routes import asistencias_bp
from routes.configuracion_routes import configuracion_bp 
from routes.usuarios_routes import usuarios_bp
from routes.socio_portal_routes import socio_portal_bp




from flask_login import LoginManager

app = Flask(__name__)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Debe iniciar sesión."
login_manager.login_message_category = "warning"



@app.context_processor
def inject_periodo_actual():
    db = SessionLocal()
    try:
        # Buscamos el periodo activo o el último creado
        periodo = db.query(Periodo).order_by(Periodo.id.desc()).first()
        
        if periodo:
            return {
                'periodo_actual': f"{periodo.anio}-{periodo.mes:02d}",
                'periodo_abierto': (periodo.cerrado ==False), # True o False
                'periodo_respaldo_id': periodo.id
            }
        
        return {
            'periodo_actual': "Sin Periodo",
            'periodo_abierto': False,
            'periodo_respaldo_id': None

        }
    finally:
        db.close()


@login_manager.user_loader
def load_user(user_id):

    db = SessionLocal()

    try:
        return db.get(Usuario, int(user_id))
    finally:
        db.close()

# Crear base de datos
#Base.metadata.create_all(
#    bind=engine
#)

# registrar  blueprints en al app
app.secret_key = "BK_FAM_2026"
app.register_blueprint(auth_bp)
app.register_blueprint(utilidades_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(prestamos_bp)
app.register_blueprint(socios_bp)
app.register_blueprint(periodos_bp)
app.register_blueprint(acciones_bp)
app.register_blueprint(movimientos_bp)
app.register_blueprint(solicitudes_bp)
app.register_blueprint(distribucion_bp)
app.register_blueprint(asistencias_bp)
app.register_blueprint(configuracion_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(socio_portal_bp)




if __name__ == "__main__":
    app.run(debug=True)