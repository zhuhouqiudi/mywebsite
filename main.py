import os
import urllib
import cgi

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.api import memcache

import jinja2
import webapp2
import datetime
import re
import string


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class Questionlist(db.Model):
	ownername = db.StringProperty()
	ownerid = db.StringProperty()
	questionname = db.StringProperty()
	content = db.TextProperty(default = "")
	questionvote = db.IntegerProperty(default=0)
	questionuplist = db.ListProperty(str)
	questiondownlist = db.ListProperty(str)
	tagstr = db.StringProperty()
	taginquestionlist = db.ListProperty(str)
	modify_time = db.DateTimeProperty(auto_now=True)
	created_time = db.DateTimeProperty(auto_now_add=True) 
	def tagList(self):
	    return [Taglist.get(key) for key in self.taginquestionlist]
	def modifytimeinEST(self):
            return self.modify_time + datetime.timedelta(hours=-5)
        def contentFormat(self):    
            return content_filter(self.content)

class Answerlist(db.Model):
	ownername = db.StringProperty()
	ownerid = db.StringProperty()
	answercontent = db.TextProperty(default = "")
	answervote = db.IntegerProperty(default=0)
	answeruplist = db.ListProperty(str)
	answerdownlist = db.ListProperty(str)
	created_time = db.DateTimeProperty(auto_now_add=True)
	modify_time = db.DateTimeProperty(auto_now=True)
	def modifytimeinEST(self):
            return self.modify_time + datetime.timedelta(hours=-5)
        def contentFormat(self):  
            return content_filter(self.answercontent)

def content_filter(str): #replace links and picturen links in text content with HTML link or picture
    str = re.sub(r'(https?)(://[\w:;/.?%#&=+-]+)(\.(jpg|png|gif))', imageReplacer, str)
    str = re.sub(r'(?<!")(https?)(://[\w:;/.?%#&=+-]+)', urlReplacer, str)
    str = str.replace('\r\n', '\n')
    str = str.replace('\n','<br />\n')
    str = displayImages(str)
    return str

def urlReplacer(match, limit =40):
    return '<a href="%s">%s</a>' % (match.group(), match.group()[:limit] + ('...' if len(match.group()) > limit else ''))

def imageReplacer(match):
    return '<div><image src="%s" alt="loading image.."></div>' % match.group()

def displayImages(str):
    return re.sub(r'\[img:(.*)\]', r'<img src="/image/\1" style="max-width:400px">', str)

class Taglist(db.Model):
    tag = db.StringProperty()


class MainPage(webapp2.RequestHandler):
    def get(self):
    	user = users.get_current_user()
    	username = user.nickname()  
        questions = Questionlist.all()
        tags = Taglist.all()
        questions.order("-created_time")
        if user:
            url = users.create_logout_url('/')
            url_linktext = user.nickname() + ' -> Logout'
        else:
            url = users.create_login_url('/')
            url_linktext = 'Login'

        cursor = self.request.get('cursor')
        if cursor: 
            posts.with_cursor(start_cursor=cursor)
        items = questions.fetch(10)
        if len(items) < 10:      
            cursor = None     # indicate this is last page
        else:
            cursor = questions.cursor()

        template_values = {
            'tags': tags,
            'username': username,
            'cursor': cursor,
            'url': url,
            'url_linktext': url_linktext,
            'questions': items,
        }
        template = JINJA_ENVIRONMENT.get_template('MainPage.html')
        self.response.write(template.render(template_values))


class CreateQuestion(webapp2.RequestHandler):
    def get(self):        
        user = users.get_current_user()
        if user:
            template = JINJA_ENVIRONMENT.get_template('createquestion.html')
            self.response.write(template.render())
        else:
            self.redirect(users.create_login_url('/'))
    
    def post(self):
    	user = users.get_current_user()
    	ownerid = user.user_id()
    	ownername = user.nickname()  
        questionname = self.request.get('questionname')
        content = self.request.get('content') 
        tagstr = self.request.get('tags')

        if questionname and content:
            taglist = re.split('[,; ]+', tagstr)   
            taginquestionlist = []
            for tagstr in taglist:      # store Tag entity into datastore and they will have key
                tag = Taglist.all().filter('tag =', tagstr).get()
                if tag == None:         # if this is not None, then the tag is used before
                   tag = Taglist(tag=tagstr)
                   tag.put()
                taginquestionlist.append(tag.key())          
            question = Questionlist( tagstr = tagstr, ownerid = ownerid, ownername = ownername, questionname = questionname, content = content, taginquestionlist=taginquestionlist)
            question.created_time = question.created_time + datetime.timedelta(hours=-5)
            question.put()
        self.redirect('/') 

class EditQuestion(webapp2.RequestHandler):
    def get(self, questionkey):
        user = users.get_current_user()
        question = Questionlist.get_by_id(int(questionkey))
	if user:
	   if question.ownername == user.nickname():
	      template = JINJA_ENVIRONMENT.get_template('editquestion.html')
              self.response.write(template.render({'questionkey': questionkey, 'prequestionname':question.questionname, 'precontent':question.content, 'pretagstr': question.tagstr}))
           else:
               template = JINJA_ENVIRONMENT.get_template('error.html')
               self.response.write(template.render({'dir': 'question','key': questionkey}))
        else:
            self.redirect(users.create_login_url('/editquestion/%s' % questionkey))
    def post(self, questionkey):
    	question = Questionlist.get_by_id(int(questionkey))
        question.questionname = self.request.get('questionname')
        question.content = self.request.get('content')
        question.tagstr = self.request.get('tagstr')
        question.taginquestionlist = [var for var in question.tagstr.split(",")]
        question.modify_time = question.modify_time + datetime.timedelta(hours=-5)
        question.put()     #update entity
        self.redirect('/view/%s' %questionkey)
  

class View (webapp2.RequestHandler):
    def get(self, questionkey):
    	user = users.get_current_user()
    	userid = user.user_id()
    	username = user.nickname()  
        question = Questionlist.get_by_id(int(questionkey))
        answers = Answerlist.all()
        answers.order("-answervote")
        answers.ancestor(question)

        cursor = self.request.get('cursor')
        if cursor: 
           answers.with_cursor(start_cursor=cursor)
        items = answers.fetch(10)
        if len(items) < 10:      
           cursor = None    
        else:
            cursor = answers.cursor()

        template_values = {'cursor': cursor,'userid': userid, 'username': username, 'questionkey': questionkey, 'question': question, 'answers': items}
        template = JINJA_ENVIRONMENT.get_template('view.html')
        self.response.write(template.render(template_values))

    def post(self, questionkey):
    	user = users.get_current_user()
    	username = user.nickname
    	question = Questionlist.get_by_id(int(questionkey))
        answer = Answerlist(parent=question)         
        answer.answercontent = self.request.get('content')
        answer.ownername = self.request.get('ownername')
        answer.created_time = answer.created_time + datetime.timedelta(hours=-5)
        answer.modify_time = answer.modify_time + datetime.timedelta(hours=-5)
    	
        if answer.answercontent and answer.ownername:
            answer.put()
        self.redirect('/view/%s' % questionkey) 

class EditAnswer(webapp2.RequestHandler):
    def get(self, answerkey):
        user = users.get_current_user()
        answer = Answerlist.get(answerkey)
        questionkey = answer.parent_key().id()
        question = Questionlist.get_by_id(int(answer.parent_key().id()))
        if user:
           if answer.ownername == user.nickname():
              template = JINJA_ENVIRONMENT.get_template('editanswer.html')
              self.response.write(template.render({'question': question, 'questionkey': questionkey, 'answerkey': answerkey, 'preanswercontent':answer.answercontent,}))
           else:
               template = JINJA_ENVIRONMENT.get_template('error.html')
               self.response.write(template.render({'dir': 'answer','key': answerkey}))
        else:
            self.redirect(users.create_login_url('/editanswer/%s' % answerkey))
    def post(self, answerkey):
        answer = Answerlist.get(answerkey)
        answer.answercontent = self.request.get('answercontent')
        questionkey = answer.parent_key().id()
        answer.put()     
        self.redirect('/view/%s' %questionkey)

class Vote(webapp2.RequestHandler):
    def get(self, name, key):
	user = users.get_current_user()
        if user:
	   userid = user.user_id()
	   if name == "questionvote":
	      question = Questionlist.get_by_id(int(key))
	      attitude = self.request.get('questionvote')
	      if attitude == "Up":
	         if userid in question.questionuplist:
	   	    question.questionvote = question.questionvote 
	         else:
	   	    question.questionvote = question.questionvote + 1
	   	    question.questionuplist.append(userid)
	   	    if userid in question.questiondownlist:
	   	       question.questionvote = question.questionvote + 1
	   	       question.questiondownlist.remove(userid)
              elif attitude == "Down":
        	   if userid in question.questiondownlist:
                      question.questionvote = question.questionvote
                   else: 
                      question.questionvote = question.questionvote - 1
                      question.questiondownlist.append(userid)
                      if userid in question.questionuplist:
                         question.questionvote = question.questionvote - 1     	
	   	         question.questionuplist.remove(userid)
	      questionkey = key
	      question.put()

           elif name == "answervote":
	        answer = Answerlist.get(key)
	        attitude = self.request.get('answervote')
	        if attitude == "Up":
	     	   if userid in answer.answeruplist:
	     	      answer.answervote = answer.answervote
	     	   else:
	     	      answer.answervote = answer.answervote + 1
	     	      answer.answeruplist.append(userid)
	     	      if userid in answer.answerdownlist:
	     	      	 answer.answervote = answer.answervote + 1
	     	         answer.answerdownlist.remove(userid)
	        elif attitude == "Down":
	     	     if userid in answer.answerdownlist:
	     	        answer.answervote = answer.answervote
	     	     else:
	     	        answer.answervote = answer.answervote - 1
	     	        answer.answerdownlist.append(userid)
	     	        if userid in answer.answeruplist:
	     	           answer.answervote = answer.answervote - 1
	     	     	   answer.answeruplist.remove(userid)
	        questionkey = answer.parent_key().id()
	        answer.put()
        self.redirect('/view/%s' %questionkey)

class TagView(webapp2.RequestHandler):
    def get(self, tagkey):
	user = users.get_current_user()
    	username = user.nickname()  
    	tag = Taglist.get(tagkey)
        questions = Questionlist.all()
        questions.order("-created_time")

        cursor = self.request.get('cursor')
        if cursor: 
            posts.with_cursor(start_cursor=cursor)
        items = questions.fetch(10)
        if len(items) < 10:      
            cursor = None     # indicate this is last page
        else:
            cursor = questions.cursor()

        template_values = {
            'username': username,
            'tag': tag,
            'cursor': cursor,
            'questions': items,
        }
        template = JINJA_ENVIRONMENT.get_template('TagView.html')
        self.response.write(template.render(template_values))



class RssHandler(webapp2.RequestHandler):
    def get(self, questionkey):
        question = Questionlist.get_by_id(int(questionkey))    
        answers = Answerlist.all()
        answers.ancestor(question)        
        answers.order("-answervote")
        template = JINJA_ENVIRONMENT.get_template('rss.xml')
        self.response.write(template.render({'question': question,'answers': answers,}))
		


application = webapp2.WSGIApplication([
	('/', MainPage),
	('/createquestion', CreateQuestion),
	('/view/(.*)', View),
	('/editquestion/(.*)', EditQuestion),
	('/editanswer/(.*)', EditAnswer),
	('/vote/(.*)/(.*)', Vote),
	('/tagview/(.*)', TagView),
	#('/rss/(.*)', RssHandler),
	], debug = True)
