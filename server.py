
"""
Columbia's COMS W4111.001 Introduction to Databases
Example Webserver
To run locally:
    python server.py
Go to http://localhost:8111 in your browser.
A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""
import os
  # accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, url_for
from wtform_fields import *
from User import User
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from datetime import datetime

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

# configure flask login
login = LoginManager(app)
login.init_app(app)

#
# The following is a dummy URI that does not connect to a valid database. You will need to modify it to connect to your Part 2 database in order to use the data.
#
# XXX: The URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@34.75.150.200/proj1part2
#
# For example, if you had username gravano and password foobar, then the following line would be:
#
#     DATABASEURI = "postgresql://gravano:foobar@34.75.150.200/proj1part2"
#
DATABASEURI = "postgresql://sw3449:6294@34.75.150.200/proj1part2"


#
# This line creates a database engine that knows how to connect to the URI above.
#
engine = create_engine(DATABASEURI)


@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request 
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request.

  The variable g is globally accessible.
  """
  try:
    g.conn = engine.connect()
  except:
    print("uh oh, problem connecting to database")
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  """
  At the end of the web request, this makes sure to close the database connection.
  If you don't, the database could run out of memory!
  """
  try:
    g.conn.close()
  except Exception as e:
    pass

@app.route('/')
def base():
  return render_template("base.html")


#---------------------------------------Register and Login ---------------------------------------------#
@app.route('/register', methods=['GET','POST'])
def register():
  reg_form = RegistrationForm()
  if reg_form.validate_on_submit():
    username = reg_form.username.data
    password = reg_form.password.data

    # check if username exits
    user_object = User(username, password)
    if is_registered_user(user_object):
      return "Someone else has taken this username!"
    else:
      register_user(user_object)
      return redirect(url_for('login'))

  return render_template("register.html", form=reg_form)

# insert the new user data into database
def register_user(user):
  cursor = g.conn.execute("INSERT INTO Users (username, password) VALUES (%s, %s)",(user.username, user.password))
  cursor.close()

# check if the user is registered or not
def is_registered_user(user):
  cursor = g.conn.execute("SELECT * FROM Users where username=%s", (user.username))
  data = cursor.fetchone()
  cursor.close()

  if data:
    return True
  else:
    return False

@login.user_loader
def load_user(username):
  cursor = g.conn.execute("SELECT * FROM Users where username=%s", (username))
  data = cursor.fetchone()
  cursor.close()

  if data is None:
    return None
  
  return User(data[1],data[2],data[0])

# check if the user exists or not
# and then check if the password is valid or not
def authenticate_user(user):
  if is_registered_user(user):
    cursor = g.conn.execute("SELECT * FROM Users where username=%s", (user.username))
    data = cursor.fetchone()
    cursor.close()

    if data[2] == user.password:
      return True
  else:
    return False

@app.route('/login', methods=['GET','POST'])
def login():
  login_form = LoginForm()
  if login_form.validate_on_submit():
    username = login_form.username.data
    password = login_form.password.data

    # check if password is correct
    user_object = User(username, password)
    if authenticate_user(user_object):
      login_user(user_object)
      return redirect(url_for('base'))
    else:
      return "Wrong username or password. Please try again!"

  return render_template("login.html", form=login_form)

@app.route("/logout", methods=['GET'])
def logout():
  logout_user()
  return redirect(url_for('base'))


#-------------------------------------------------Profile----------------------------------------------------------#
@app.route("/profile")
@login_required
def profile():
  # username for this user
  cursor = g.conn.execute("select u.username from users u where u.uid=%s",current_user.uid)
  user_name = []
  user_name = cursor.fetchone()
  cursor.close()

  # wishlist for this user
  cursor = g.conn.execute('''SELECT u.username, s.song_name, al.album_name, a.artist_name 
                              FROM wishlists w, users u, song_contain s, artists a, al_release al 
                              WHERE w.uid=u.uid AND w.song_id=s.song_id AND w.album_id=al.album_id 
                              AND w.artist_id=a.artist_id AND u.uid=%s''',current_user.uid)
  wishs = []
  wishs = cursor.fetchall()
  cursor.close()

  # online concert registration for this user order by concert time asc
  cursor = g.conn.execute('''SELECT a.artist_name, r.concert_name, r.concert_time, o.link 
                              FROM registers r, artists a, online_concerts o 
                              WHERE r.artist_id=a.artist_id AND r.artist_id=o.artist_id 
                              AND r.concert_name=o.concert_name AND r.concert_time=o.concert_time 
                              AND r.uid=%s
                              ORDER BY r.concert_time ASC''', current_user.uid)
  concert_reg = []
  concert_reg = cursor.fetchall()
  cursor.close()

  # recommendation based on this user's wishlist
  # recommend songs whose artists are of the same genre the user likes
  cursor = g.conn.execute('''
                            SELECT DISTINCT s.song_name, al.album_name, t.artist_name, s.popularity
                            FROM (SELECT artist_id, artist_name, UNNEST(genres) as g FROM artists) t 
                            JOIN Song_contain s ON t.artist_id=s.artist_id
                            JOIN Al_release al ON s.album_id=al.album_id
                            WHERE t.g IN (SELECT UNNEST(genres) FROM Artists WHERE artist_id IN (SELECT artist_id FROM Wishlists WHERE uid=%s))
                            AND s.song_id NOT IN (SELECT song_id FROM Wishlists WHERE uid=%s)
                            ORDER BY s.popularity DESC LIMIT 5 ''', current_user.uid,current_user.uid)
  
  recommendations = []
  recommendations = cursor.fetchall()
  cursor.close()

  context = dict(wishs=wishs, concert_reg=concert_reg, user_name=user_name, recommendations=recommendations)
  return render_template("profile.html", **context)


#-------------------------------------------------Search-------------------------------------------------------------#
@app.route('/search', methods=['GET','POST'])
@login_required
def search():
  search_result = []
  if request.form.get('artists') or request.form.get('songs') or request.form.get('albums'):

    artists = None if not request.form.get('artists') else request.form.get('artists')
    songs = None if not request.form.get('songs') else request.form.get('songs')
    albums = None if not request.form.get('albums') else request.form.get('albums')

    cursor = g.conn.execute('''SELECT s.song_name, al.album_name, a.artist_name, al.released_date, s.popularity 
                              FROM song_contain s, artists a, al_release al 
                              WHERE ('%s' = 'None' OR a.artist_name ILIKE '%%%%%s%%%%') 
                              AND ('%s' = 'None' or s.song_name ILIKE '%%%%%s%%%%') 
                              AND ('%s' = 'None' or al.album_name ILIKE '%%%%%s%%%%')
                              AND s.artist_id=a.artist_id AND s.album_id=al.album_id 
                              ORDER BY s.popularity desc'''% (artists, artists, songs, songs, albums, albums))
    search_result = cursor.fetchall()
    cursor.close()
  
  else:
    cursor = g.conn.execute("SELECT s.song_name, al.album_name, a.artist_name, al.released_date, s.popularity FROM song_contain s, artists a, al_release al WHERE s.artist_id=a.artist_id AND s.album_id=al.album_id ORDER BY s.popularity desc LIMIT 5")
    search_result = cursor.fetchall()
    cursor.close()

  context = dict(search_result=search_result)
  
  return render_template("search.html", **context)


#--------------------------------------------------Review------------------------------------------------------#
@app.route("/review", methods=['GET','POST'])
@login_required
def review():
  # reviews of certain song by search
  reviews = []
  if request.form.get('songs'):
    songs = request.form.get('songs')

    cursor = g.conn.execute('''SELECT s.song_id, s.song_name, a.artist_name, u.username, r.review_text, r.rating, to_char(r.review_time, 'Month DD YYYY')
                                FROM song_contain s JOIN artists a ON s.artist_id=a.artist_id
                                LEFT JOIN review_rates r ON r.song_id=s.song_id
                                LEFT JOIN users u ON  r.uid=u.uid 
                                WHERE s.song_name ILIKE '%%%%%s%%%%' ''' % (songs))
    reviews = cursor.fetchall()
    cursor.close()
  
  else:
    # top 5 reviews order by review_time desc
    cursor = g.conn.execute('''SELECT s.song_id, s.song_name, a.artist_name, u.username, r.review_text, r.rating, to_char(r.review_time, 'Month DD YYYY') 
                              FROM review_rates r, users u, song_contain s, artists a 
                              WHERE r.uid=u.uid AND r.song_id=s.song_id AND r.artist_id=a.artist_id
                              ORDER BY r.review_time DESC LIMIT 5''')
    reviews = cursor.fetchall()
    cursor.close()

  # average ratings
  song_ratings = []
  cursor = g.conn.execute('''SELECT s.song_id, s.song_name, a.artist_name, ROUND(avg(r.rating),2) as avg_rating
                              FROM review_rates r, song_contain s, artists a 
                              WHERE r.song_id=s.song_id AND r.artist_id=a.artist_id
                              GROUP BY s.song_id,s.song_name, a.artist_name''')
  song_ratings = cursor.fetchall()
  cursor.close()

  # song_id and its associated album_id, artist_id
  song_info = []
  cursor = g.conn.execute("select song_id, album_id, artist_id from song_contain")
  song_info = cursor.fetchall()
  cursor.close()

  # username for this user
  cursor = g.conn.execute("select u.username from users u where u.uid=%s",current_user.uid)
  user_name = []
  user_name = cursor.fetchone()
  cursor.close()

  context = dict(reviews=reviews, song_ratings=song_ratings, song_info=song_info, user_name=user_name)
  return render_template("review.html", **context)

@app.route('/write_review', methods=['POST'])
def write_review():
  uid = current_user.uid
  review_time = datetime.now()

  # check if the user has already reviewed the song. if yes, update the review, if no, add new review
  result = g.conn.execute('''UPDATE Review_Rates 
                              SET rating=%s, review_text=%s, review_time=%s 
                              WHERE uid=%s AND song_id=%s''', (request.form['rating'], request.form['text'], review_time, uid, request.form['song_id']))

  if result.rowcount == 0:
    g.conn.execute('''INSERT INTO Review_Rates (uid, song_id, album_id, artist_id, review_time, review_text, rating) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)''', (uid, request.form['song_id'], request.form['album_id'], request.form['artist_id'], review_time, request.form['text'], request.form['rating']))

  return redirect('/review')

@app.route('/add_to_wishlist', methods=['POST'])
def add_to_wishlist():
  uid = current_user.uid
  song_id = request.form['song_id']

  result = g.conn.execute('''UPDATE Wishlists
                              SET uid=%s
                              WHERE uid=%s and song_id=%s''', (uid, uid, song_id))
  
  # check if the song is already in wishlist or not. if not, add it to the wishlist
  if result.rowcount == 0:
    g.conn.execute('''INSERT INTO Wishlists (uid, song_id, album_id, artist_id)
                      VALUES (%s, %s, %s, %s)''', (uid, song_id, request.form['album_id'], request.form['artist_id']))
    
  return redirect('/review')


#------------------------------------------------Online concert------------------------------------------------------#
@app.route("/concert", methods=['GET','POST'])
@login_required
def concert():
  # today's datetime
  now_date = datetime.now()

  # future concerts information of certain artist by search
  concerts = []
  if request.form.get('artists'):
    artists = request.form.get('artists')

    cursor = g.conn.execute('''SELECT a.artist_id, a.artist_name, o.concert_name, o.concert_time, o.link
                                FROM online_concerts o JOIN artists a ON o.artist_id=a.artist_id
                                WHERE a.artist_name ILIKE '%%%%%s%%%%' 
                                AND o.concert_time > %s ''' % (artists, now_date))
    concerts = cursor.fetchall()
    cursor.close()
  
  else:
    # all future online concerts order by concert_time asc
    cursor = g.conn.execute('''SELECT a.artist_id, a.artist_name, o.concert_name, o.concert_time, o.link
                              FROM online_concerts o, artists a 
                              WHERE o.artist_id=a.artist_id
                              AND o.concert_time > %s
                              ORDER BY o.concert_time ASC''', now_date)
    concerts = cursor.fetchall()
    cursor.close()
  
  # concert_name, concert_time and artist_id
  concert_info = []
  cursor = g.conn.execute("select artist_id, concert_name, concert_time from online_concerts")
  concert_info = cursor.fetchall()
  cursor.close()

  # username for this user
  cursor = g.conn.execute("select u.username from users u where u.uid=%s",current_user.uid)
  user_name = []
  user_name = cursor.fetchone()
  cursor.close()

  context = dict(concerts=concerts, concert_info=concert_info, user_name=user_name)
  return render_template("concert.html", **context)

@app.route("/register_concert", methods=['POST'])
def register_concert():
  uid = current_user.uid
  cname = request.form['concert_name']
  ctime = request.form['concert_time']

  result = g.conn.execute('''UPDATE registers
                              SET uid=%s
                              WHERE uid=%s and concert_name=%s and concert_time=%s''', (uid, uid, cname, ctime))
  
  # check if the user has already registered for the online concert or not. if not, register
  if result.rowcount == 0:
    g.conn.execute('''INSERT INTO registers (artist_id, concert_name, concert_time, uid)
                      VALUES (%s, %s, %s, %s)''', (request.form['artist_id'], cname, ctime, uid))
    
  return redirect('/concert')




if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    """
    This function handles command line parameters.
    Run the server using:

        python server.py

    Show the help text using:

        python server.py --help

    """
    app.secret_key = 'hello'

    HOST, PORT = host, port
    print("running on %s:%d" % (HOST, PORT))
    app.run(host=HOST, port=PORT, debug=True, threaded=threaded)

  run()
