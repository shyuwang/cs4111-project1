from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired

class RegistrationForm(FlaskForm):
    """ Registration form """
    username = StringField('username_label', validators=[InputRequired(message="Username required")])
    password = PasswordField('password_label', validators=[InputRequired(message="Password required")])
    submit_button = SubmitField('Create')

class LoginForm(FlaskForm):
    """ Login Form """
    username = StringField('username_label', validators=[InputRequired(message="Username required")])
    password = PasswordField('password_label',validators=[InputRequired(message="Password required")])
    submit_button = SubmitField('Login')



