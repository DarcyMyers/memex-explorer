from __future__ import unicode_literals

import os
import urllib2
import yaml
import pytest
from yaml import load as yaml_load
from yaml import Loader, SafeLoader

from django.conf import settings

def construct_yaml_str(self, node):
    # Override the default string handling function 
    # to always return unicode objects
    return self.construct_scalar(node)
Loader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)
SafeLoader.add_constructor(u'tag:yaml.org,2002:str', construct_yaml_str)

# Test
from memex.test_utils.unit_test_utils import UnitTestSkeleton, form_errors, get_object
from django.test import TestCase
from django.db import IntegrityError

# App
from base.forms import AddProjectForm
from base.models import * #TODO: fix this. Explicitly list models.


class TestViews(UnitTestSkeleton):

    @classmethod
    def setUpClass(cls):
        super(TestViews, cls).setUpClass()

        cls.test_project = Project(
            name = "Project Test",
            description = "Test Project Description")
        cls.test_project.save()

    def test_front_page(self):
        response = self.get('base:index')
        assert 'base/index.html' in response.template_name


    def test_about_page(self):
        response = self.get('base:about')
        assert 'base/about.html' in response.template_name

    def test_documentation(self):
        response = urllib2.urlopen("http://memex-explorer.readthedocs.org/en/latest/")
        assert response.code == 200

    def test_add_project_page(self):
        response = self.get('base:add_project')
        assert 'base/add_project.html' in response.template_name


    def test_add_project_no_name(self):
        response = self.post('base:add_project',
            {'description': 'cats cats cats'})
        assert 'This field is required.' in form_errors(response)['name']


    def test_add_project_success(self):
        response = self.post('base:add_project',
            {'name': 'CATS',
             'description': 'cats cats cats'})
        assert 'base/project.html' in response.template_name
        assert b'CATS' in response.content

    def test_project_page(self):
        response = self.get('base:project',
            slugs={'project_slug': self.test_project.slug})
        assert 'base/project.html' in response.template_name

    def test_project_settings_page(self):
        response = self.get('base:project_settings', 
            slugs={'project_slug': self.test_project.slug})
        assert 'base/project_update_form.html' in response.template_name

    def test_project_settings_change_name(self):
        response = self.post('base:project_settings',
                {'name': 'Cat Project'}, slugs={'project_slug': self.test_project.slug}, )
        project = get_object(response)
        assert project.name == 'Cat Project'

    def test_project_settings_change_description(self):
        response = self.post('base:project_settings',
                {'description': 'A project for cats!'}, slugs={'project_slug': self.test_project.slug}, )
        project = get_object(response)
        assert project.description == 'A project for cats!'

    def test_project_settings_change_description(self):
        response = self.post('base:delete_project', slugs={'project_slug': self.test_project.slug})
        assert 'base/index.html' in response.template_name

class TestForms(TestCase):

    def setUp(self):
        self.project = Project.objects.create(name="Bicycles for sale", description="Project about bicycles")

    def test_project_form(self):
        form_data = {
            'name': 'CATS',
            'description': 'cats cats cats'}
        form = AddProjectForm(data=form_data)
        assert form.is_valid()

    def test_project_form_no_name(self):
        form_data = {
            'description': 'cats cats cats'}
        form = AddProjectForm(data=form_data)
        assert form.is_valid() is False
        assert 'This field is required.' in form.errors['name']

    def test_existing_project_error(self):
        form_data = {
            'name': 'Bicycles for sale',
            'description': 'cats cats cats'}
        form = AddProjectForm(data=form_data)
        assert form.is_valid() is False
        assert 'Project with this Name already exists.' in form.errors['name']


class TestProjectQueries(TestCase):

    def setUp(self):
        project = Project.objects.create(name=u"Bicycles for sale", description="Project about bicycles")
        self.project = project

    def test_project_exists(self):
        assert Project.objects.get(name="Bicycles for sale")

    def test_unique_project(self):
        with self.assertRaises(IntegrityError):
            Project.objects.create(name="Bicycles for sale", description="Project about bicycles")

    def test_get_by_slug(self):
        assert 'bicycles-for-sale' == self.project.slug


#run this with cd ~/memex-explorer && py.test --pdb -s -m docker
@pytest.mark.docker
class TestDockerSetup(TestCase):

    maxDiff = None

    @classmethod
    def tearDownClass(cls):
        AppPort.objects.filter(app__name__in=['tika', 'elasticsearch', 'kibana']).delete()
        VolumeMount.objects.filter(app__name__in=['tika', 'elasticsearch', 'kibana']).delete()
        EnvVar.objects.filter(app__name__in=['tika', 'elasticsearch', 'kibana']).delete()
        AppLink.objects.filter(from_app__name__in=['tika', 'elasticsearch', 'kibana']).delete()
        App.objects.filter(name__in=['tika', 'elasticsearch', 'kibana']).delete()
        os.remove(os.path.join(settings.BASE_DIR, 'base/nginx-reverse-proxy.conf'))
        os.remove(os.path.join(settings.BASE_DIR, 'base/docker-compose.yml'))

    @classmethod
    def setUpClass(cls):
        tika=App.objects.create(
            name='tika',
            image='continuumio/tika'
        )
        AppPort.objects.create(
            app = tika,
            internal_port = 9998
        )
        elasticsearch = App.objects.create(
            name='elasticsearch',
            image='elasticsearch'
        )
        AppPort.objects.create(
            app = elasticsearch,
            internal_port = 9200
        )
        AppPort.objects.create(
            app = elasticsearch,
            internal_port = 9300
        )
        VolumeMount.objects.create(
            app = elasticsearch,
            mounted_at = '/data',
            located_at = os.path.join(settings.BASE_DIR, '/home/ubuntu/elasticsearch/data'),
        )
        kibana = App.objects.create(
            name = 'kibana',
            image = 'continuumio/kibana',
        )
        AppPort.objects.create(
            app = kibana,
            internal_port = 80,
            expose_publicly = True,
        )
        EnvVar.objects.create(
            app = kibana,
            name='KIBANA_SECURE',
            value='false'
        )
        AppLink.objects.create(
            from_app = kibana,
            to_app = elasticsearch,
            alias = 'es'
        )
        project = Project.objects.create(
            name='test1',
            slug='test1_slug'
        )
        cls.tika_container = tika.create_container_entry(project)
        cls.es_container = elasticsearch.create_container_entry(project)
        cls.kibana_container = kibana.create_container_entry(project)
        cls.tika_app = tika
        cls.es_app = elasticsearch
        cls.kibana_app = kibana
        cls.kibana_container.high_port = 46666
        cls.kibana_container.save()

    def test_kibana_container_urlbase(self):
        self.assertEqual(self.kibana_container.public_urlbase(), '/test1/kibana')

    def test_kibana_container_name(self):
        self.assertEqual(os.path.basename(os.path.dirname(Container.DOCKER_COMPOSE_DESTINATION_PATH)), 'base')
        self.assertEqual(self.kibana_container.docker_name(), 'base_test1kibana_1')

    def test_generate_docker_compose(self):
        context = Container.generate_container_context()
        Container.fill_template(Container.DOCKER_COMPOSE_TEMPLATE_PATH, Container.DOCKER_COMPOSE_DESTINATION_PATH, context)
        container_yml = open(Container.DOCKER_COMPOSE_DESTINATION_PATH, 'r').read()
        print(container_yml)

        self.assertIn('KIBANA_SECURE=false', container_yml)
        data = yaml_load(container_yml)
        correct_data = {
            'test1tika': {
                'image': 'continuumio/tika',
                'ports': [
                    '9998',
                ]
            },
            'test1elasticsearch': {
                'image': 'elasticsearch',
                'volumes': [
                    '/home/ubuntu/elasticsearch/data:/data',
                ],
                'ports': [
                    '9200',
                    '9300',
                ],
            },
            'test1kibana':{
                'image': 'continuumio/kibana',
                'ports': [
                    '80',
                ],
                'links': [
                    'test1elasticsearch:es',
                ],
                'environment':[
                    'KIBANA_SECURE=false',
                ],
            },
        }
        self.assertEqual(data, correct_data)

    def skip_test_launch_single_container(self):
        import tempfile
        import os
        import subprocess
        with tempfile.NamedTemporaryFile(delete=True) as f:
            self.assertTrue(os.path.exists(f.name))
            f.write(yaml_dump({'test2tika': {
                'image': 'continuumio/tika',
                'ports': [
                    '9998',
                ]
            }}))
            f.flush()
            create_command = ['sudo', Container.docker_compose_path(), '-f', f.name, 'up', '-d']
            os.subprocess.check_output(create_command)
            docker_name = "{}_{}_1".format(os.path.dirname(os.path.basename(f.name)), 'test2tika')
            port_command = ['sudo', 'docker', 'port', docker_name]
            port_response = os.subprocess.check_output(port_command)
            self.assert_in('9998/tcp -> 0.0.0.0:', port_response)
            self.assert_equal(port_response.split('/tcp -> 0.0.0.0:')[0], '9998')

    def test_generate_nginx_context(self):
        context = Container.generate_nginx_context([('/test1/kibana',46666),])
        self.assertEqual(context['static_root'], settings.STATIC_ROOT)


    def test_generate_nginx_config(self):
        context = Container.generate_nginx_context([('/test1/kibana',46666),])
        Container.fill_template(Container.NGINX_CONFIG_TEMPLATE_PATH, Container.NGINX_CONFIG_DESTINATION_PATH, context)
        data = '\n'+ open(Container.NGINX_CONFIG_DESTINATION_PATH, 'r').read()
        correct_data = """
server {
    listen 80;
    server_name example.com 0.0.0.0;
    client_max_body_size 100M;

    location / {
        proxy_pass http://0.0.0.0:8000/;
    }

    location /static/ {
        rewrite ^/static/(.*)$ /$1 break;
        root %s/;
    }

    location /test1/kibana/ {
        rewrite /test1/kibana/(.*) /$1 break;
        proxy_pass          http://0.0.0.0:46666/;
        proxy_redirect      off;
        proxy_set_header    Host $host;
    }
}""" % settings.STATIC_ROOT
        self.assertEqual(data, correct_data)

