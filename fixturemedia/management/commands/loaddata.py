from os.path import isdir
from os.path import join

import django.core.management.commands.loaddata
import django.core.serializers
from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import signals
from django.db.models.fields.files import FileField

# For Python < 3.3
file_not_found_error = getattr(__builtins__,'FileNotFoundError', IOError)


def models_with_filefields():
    for modelclass in apps.get_models():
        if any(isinstance(field, FileField) for field in modelclass._meta.fields):
            yield modelclass


class Command(django.core.management.commands.loaddata.Command):

    def load_images_for_signal(self, sender, **kwargs):
        instance = kwargs['instance']
        for field in sender._meta.fields:
            if not isinstance(field, FileField):
                continue
            path = getattr(instance, field.attname)
            if path is None or not path.name:
                continue
            for fixture_path in self.fixture_media_paths:
                filepath = join(fixture_path, path.name)
                try:
                    with open(filepath, 'rb') as f:
                        default_storage.save(path.name, f)
                except file_not_found_error:
                    self.stderr.write("Expected file at {} doesn't exist, skipping".format(filepath))
                    continue

    def handle(self, *fixture_labels, **options):
        # Hook up pre_save events for all the apps' models that have FileFields.
        for modelclass in models_with_filefields():
            signals.pre_save.connect(self.load_images_for_signal, sender=modelclass)

        fixture_paths = self.find_fixture_paths()
        fixture_paths = (join(path, 'media') for path in fixture_paths)
        fixture_paths = [path for path in fixture_paths if isdir(path)]
        self.fixture_media_paths = fixture_paths

        return super(Command, self).handle(*fixture_labels, **options)

    def find_fixture_paths(self):
        """Return the full paths to all possible fixture directories."""
        app_fixtures = [join(config.path, 'fixtures') for config in apps.app_configs.values()]

        return app_fixtures + list(settings.FIXTURE_DIRS)
