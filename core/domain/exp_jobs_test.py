# coding: utf-8
#
# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Jobs for explorations."""

__author__ = 'Frederik Creemers'

"""Tests for ExpSummary continuous computations."""

from core import jobs_registry
from core.domain import exp_domain
from core.domain import exp_jobs
from core.domain import rights_manager
from core.platform import models
from core.tests import test_utils
(job_models, exp_models,) = models.Registry.import_models([
   models.NAMES.job, models.NAMES.exploration])
search_services = models.Registry.import_search_services()
import feconf


class ActivitySummariesCreationOneOffJobTest(test_utils.GenericTestBase):
    """Tests for ExpSummary aggregations."""

    ONE_OFF_JOB_MANAGERS_FOR_TESTS = [
        exp_jobs.ActivitySummariesCreationOneOffJob]

    def test_all_exps_publicized(self):
        """Test exploration summary batch job if all explorations are
        publicized.
        """

        # specify explorations that will be used in test
        exp_specs = [
            {'category': 'Category A',
             'title': 'Title 1'},
             {'category': 'Category B',
            'title': 'Title 2'},
            {'category': 'Category C',
             'title': 'Title 3'},
            {'category': 'Category A',
             'title': 'Title 4'},
            {'category': 'Category C',
             'title': 'Title 5'}
            ]

        self._run_batch_job_once_and_verify_output(
            exp_specs,
            default_status=feconf.ACTIVITY_STATUS_PUBLICIZED)

    def test_all_exps_public(self):
        """Test summary batch job if all explorations are public
        but not publicized."""

        exp_specs = [
            {'category': 'Category A',
             'title': 'Title 1'},
            {'category': 'Category B',
             'title': 'Title 2'},
            {'category': 'Category C',
             'title': 'Title 3'},
            {'category': 'Category A',
             'title': 'Title 4'},
            {'category': 'Category C',
             'title': 'Title 5'}]

        self._run_batch_job_once_and_verify_output(
            exp_specs,
            default_status=feconf.ACTIVITY_STATUS_PUBLIC)

    def test_exps_some_publicized(self):
        """Test summary batch job if some explorations are publicized."""

        exp_specs = [
            {'category': 'Category A',
             'status': feconf.ACTIVITY_STATUS_PUBLIC,
             'title': 'Title 1'},
            {'category': 'Category B',
             'status': feconf.ACTIVITY_STATUS_PUBLICIZED,
             'title': 'Title 2'},
            {'category': 'Category C',
             'status': feconf.ACTIVITY_STATUS_PRIVATE,
             'title': 'Title 3'},
            {'category': 'Category A',
             'status': feconf.ACTIVITY_STATUS_PUBLICIZED,
             'title': 'Title 4'},
            {'category': 'Category C',
             'status': feconf.ACTIVITY_STATUS_PUBLICIZED,
             'title': 'Title 5'}]

        self._run_batch_job_once_and_verify_output(exp_specs)

    def _run_batch_job_once_and_verify_output(
            self, exp_specs,
            default_title='A title',
            default_category='A category',
            default_status=feconf.ACTIVITY_STATUS_PUBLICIZED):
        """Run batch job for creating exploration summaries once and
         verify its output. exp_specs is a list of dicts with
         exploration specifications. Allowed keys are category,
         status, title.  If a key is not specified, the default value
         is taken.
        """
        from core.domain import exp_services
        with self.swap(
                jobs_registry, 'ONE_OFF_JOB_MANAGERS',
                self.ONE_OFF_JOB_MANAGERS_FOR_TESTS):

            # default specs
            default_specs = {'title': default_title,
                             'category': default_category,
                             'status': default_status}

            self.register_editor('admin@example.com')
            self.login('admin@example.com')
            self.owner_id = self.get_user_id_from_email('admin@example.com')
            self.set_admins(['admin@example.com'])

            # create and delete an exploration (to make sure job handles
            # deleted explorations correctly)
            exp_id = '100'
            self.save_new_valid_exploration(
                exp_id,
                self.owner_id,
                title=default_specs['title'],
                category=default_specs['category'])
            exploration = exp_services.get_exploration_by_id(exp_id)
            exp_services.delete_exploration(self.owner_id, exp_id)

            # get dummy explorations
            num_exps = len(exp_specs)
            expected_summaries = []

            for ind in range(num_exps):
                exp_id = str(ind)
                spec = default_specs
                spec.update(exp_specs[ind])
                self.save_new_valid_exploration(
                    exp_id,
                    self.owner_id,
                    title=spec['title'],
                    category=spec['category'])
                exploration = exp_services.get_exploration_by_id(exp_id)

                # publish or publicize exploration
                if spec['status'] == feconf.ACTIVITY_STATUS_PUBLIC:
                    rights_manager.publish_exploration(self.owner_id, exp_id)
                elif (spec['status'] ==
                        feconf.ACTIVITY_STATUS_PUBLICIZED):
                    rights_manager.publish_exploration(self.owner_id, exp_id)
                    rights_manager.publicize_exploration(self.owner_id, exp_id)

                # do not include user_id here, so all explorations are not
                # editable for now (will be updated depending on user_id
                # in galleries)
                exp_rights_model = exp_models.ExplorationRightsModel.get(
                    exp_id)

                exploration = exp_services.get_exploration_by_id(exp_id)

                # manually create the expectated summary specifying title,
                # category, etc
                summary = exp_domain.ActivitySummary(
                    feconf.ACTIVITY_TYPE_EXPLORATION,
                    exp_id,
                    spec['title'],
                    spec['category'],
                    exploration.objective,
                    exploration.language_code,
                    exploration.skill_tags,
                    spec['status'],
                    exp_rights_model.community_owned,
                    exp_rights_model.owner_ids,
                    exp_rights_model.editor_ids,
                    exp_rights_model.viewer_ids,
                    exploration.version,
                    exploration.created_on,
                    exploration.last_updated)

                # calling constructor for fields that are not required
                # and have no default value does not work b/c
                # unspecified fields will be empty list in
                # expected_job_output but will be unspecified in
                # actual_job_output
                if exploration.skill_tags:
                    summary.skill_tags = exploration.skill_tags
                if exp_rights_model.owner_ids:
                    summary.owner_ids = exp_rights_model.owner_ids
                if exp_rights_model.editor_ids:
                    summary.editor_ids = exp_rights_model.editor_ids
                if exp_rights_model.viewer_ids:
                    summary.viewer_ids = exp_rights_model.viewer_ids
                if exploration.version:
                    summary.version = exploration.version

                expected_summaries.append(summary)

            # run batch job
            job_id = exp_jobs.ActivitySummariesCreationOneOffJob.create_new()
            exp_jobs.ActivitySummariesCreationOneOffJob.enqueue(job_id)
            self.process_and_flush_pending_tasks()

            # get job output
            actual_summaries = exp_services.get_all_activity_summaries()

            # check job output
            # TODO(sll): This duplicates _assert_summaries_are_equal() in
            # exp_services_test.ActivitySummaryQueryTests. Remove the
            # duplication.
            self.assertEqual(len(actual_summaries), len(expected_summaries))

            SIMPLE_PROPS = [
                'activity_type', 'id', 'title', 'category',
                'objective', 'language_code', 'skill_tags', 'status',
                'community_owned', 'owner_ids', 'editor_ids', 'viewer_ids',
                'version', 'activity_model_created_on',
                'activity_model_last_updated']

            for ind in range(len(actual_summaries)):
                for prop in SIMPLE_PROPS:
                    self.assertEqual(getattr(actual_summaries[ind], prop),
                                     getattr(expected_summaries[ind], prop))


class OneOffReindexExplorationsJobTest(test_utils.GenericTestBase):

    EXP_ID = 'exp_id'

    def setUp(self):
        super(OneOffReindexExplorationsJobTest, self).setUp()

        explorations = [exp_domain.Exploration.create_default_exploration(
            '%s%s' % (self.EXP_ID, i), 'title %d' % i, 'category%d' % i)
            for i in xrange(5)]

        from core.domain import exp_services
        for exp in explorations:
            exp_services.save_new_exploration('owner_id', exp)
            rights_manager.publish_exploration('owner_id', exp.id)

        self.process_and_flush_pending_tasks()

    def test_standard_operation(self):
        job_id = (exp_jobs.IndexAllExplorationsJobManager.create_new())
        exp_jobs.IndexAllExplorationsJobManager.enqueue(job_id)

        self.assertEqual(self.count_jobs_in_taskqueue(), 1)

        indexed_docs = []

        def add_docs_mock(docs, index):
            indexed_docs.extend(docs)
            from core.domain import exp_services
            self.assertEqual(index, exp_services.SEARCH_INDEX_EXPLORATIONS)

        add_docs_swap = self.swap(
            search_services, 'add_documents_to_index', add_docs_mock)

        with add_docs_swap:
            self.process_and_flush_pending_tasks()

        ids = [doc['id'] for doc in indexed_docs]
        titles = [doc['title'] for doc in indexed_docs]
        categories = [doc['category'] for doc in indexed_docs]

        for i in xrange(5):
            self.assertIn("%s%s" % (self.EXP_ID, i), ids)
            self.assertIn('title %d' % i, titles)
            self.assertIn('category%d' % i, categories)

