from flask import render_template, flash, redirect, url_for, request, current_app
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, EmptyForm, PostForm, ResetPasswordRequestForm, ResetPasswordForm, FollowForm, UnfollowForm, SearchForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import User, Post
from datetime import datetime, timezone
from app.email import send_password_reset_email
from werkzeug.utils import secure_filename
import os
import secrets
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import session

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.config['UPLOAD_FOLDER'], picture_fn)
    form_picture.save(picture_path)
    return picture_fn

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))
    # user = db.first_or_404(sa.select(User).where(User.username == current_user.username))
    user = User.query.filter_by(username=current_user.username).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = db.paginate(current_user.following_posts(), page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('index', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) if posts.has_prev else None
    # Calculate the number of posts on the current page
    num_posts_on_page = len(posts.items)
    print(f"Page: {page}, Total Items: {posts.total}, Pages: {posts.pages}, num_posts_on_page: {num_posts_on_page }")
    return render_template('index.html', title='Home', form=form,
                           posts=posts, user=user, next_url=next_url, prev_url=prev_url)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('index'))
    return render_template('login.html', title='Sign In', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    follow_form = FollowForm()
    unfollow_form = UnfollowForm()
    # posts = [
    #     {'author': user, 'body': 'Test post #1'},
    #     {'author': user, 'body': 'Test post #2'}
    # ]
    # Query posts for the given user
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', app.config['POSTS_PER_PAGE'], type=int)
    
    # Query posts for the given user
    query = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc())
    # Paginate the query
    paginated_posts = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('user.html', user=user, posts=paginated_posts.items, pagination=paginated_posts, follow_form=follow_form, unfollow_form=unfollow_form)


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        if form.image.data:
            picture_file = save_picture(form.image.data)
            current_user.image = picture_file
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        current_user.gender = form.gender.data
        db.session.commit()
        flash('Your changes have been saved.')
        # return redirect(url_for('edit_profile'))
        return redirect(url_for('user', username=current_user.username))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
        form.gender.data = current_user.gender
        form.image.data = current_user.image
    image_file = url_for('static', filename='profile_pics/' + current_user.image) if current_user.image else url_for('static', filename='profile_pics/default.png')
    return render_template('edit_profile.html', title='Edit Profile', form=form, image_file=image_file)


@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(request.referrer)
        current_user.follow(user)
        db.session.commit()
        flash(f'You are now following {username}!')
        return redirect(request.referrer)
    else:
        return redirect(url_for('index'))
    
@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(request.referrer)
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(request.referrer)
    else:
        return redirect(url_for('index'))
    
@app.route("/user/<username>/followers")
@login_required
def user_followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    followers = user.followers.all()
    follow_form = FollowForm()
    unfollow_form = UnfollowForm()
    return render_template('followers.html', user=user, followers=followers, follow_form=follow_form, unfollow_form=unfollow_form)

@app.route('/user/<username>/following')
@login_required
def user_following(username):
    user = User.query.filter_by(username=username).first_or_404()
    following = user.followed.all()
    follow_form = FollowForm()
    unfollow_form = UnfollowForm()
    return render_template('following.html', user=user, following=following, follow_form=follow_form, unfollow_form=unfollow_form)   

@app.route('/explore', methods=['GET', 'POST'])
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('explore', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('explore', page=posts.prev_num) if posts.has_prev else None
    search_form = SearchForm()
    follow_form = FollowForm()
    unfollow_form = UnfollowForm()

    if(search_form.search.data != ""):
        users = []
        if search_form.validate_on_submit():
            search_query = search_form.search.data
            users = User.query.filter(User.username.ilike(f'%{search_query}%'), User.id != current_user.id).all()
            return render_template('explore.html', search_form=search_form, users=users, follow_form=follow_form, unfollow_form=unfollow_form)
    return render_template("explore.html", title='Explore', posts=posts.items, next_url=next_url, prev_url=prev_url, search_form=search_form, users=users)

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.email == form.email.data))
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)


@app.route('/messages')
@login_required
def messages():
    search_form = SearchForm()
    return render_template('messages.html', search_form=search_form)