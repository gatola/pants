# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import xml.etree.ElementTree as ET

from pants.util.contextutil import open_zip
from pants_test.backend.jvm.tasks.jvm_compile.base_compile_integration_test import BaseCompileIT


SHAPELESS_CLSFILE = 'org/pantsbuild/testproject/unicode/shapeless/ShapelessExample.class'
SHAPELESS_TARGET = 'testprojects/src/scala/org/pantsbuild/testproject/unicode/shapeless'


class ZincCompileIntegrationTest(BaseCompileIT):

  def test_scala_compile_jar(self):
    jar_suffix = 'z.jar'
    with self.do_test_compile(SHAPELESS_TARGET,
                              expected_files=[jar_suffix]) as found:
      with open_zip(self.get_only(found, jar_suffix), 'r') as jar:
        self.assertTrue(jar.getinfo(SHAPELESS_CLSFILE),
                        'Expected a jar containing the expected class.')

  def test_scala_empty_compile(self):
    with self.do_test_compile('testprojects/src/scala/org/pantsbuild/testproject/emptyscala',
                              expected_files=[]) as found:
      # no classes generated by this target
      pass

  def test_scala_shared_sources(self):
    clsname = 'SharedSources.class'

    with self.do_test_compile('testprojects/src/scala/org/pantsbuild/testproject/sharedsources::',
                              expected_files=[clsname]) as found:
      classes = found[clsname]
      self.assertEqual(2, len(classes))
      for cls in classes:
        self.assertTrue(cls.endswith(
          'org/pantsbuild/testproject/sharedsources/SharedSources.class'))

  def test_scala_failure(self):
    """With no initial analysis, a failed compilation shouldn't leave anything behind."""
    analysis_file = 'testprojects.src.scala.' \
        'org.pantsbuild.testproject.compilation_failure.compilation_failure.analysis'
    with self.do_test_compile('testprojects/src/scala/org/pantsbuild/testprojects/compilation_failure',
                              expected_files=[analysis_file],
                              expect_failure=True) as found:
      self.assertEqual(0, len(found[analysis_file]))

  def test_scala_with_java_sources_compile(self):
    with self.do_test_compile('testprojects/src/scala/org/pantsbuild/testproject/javasources',
                              expected_files=['ScalaWithJavaSources.class',
                                              'JavaSource.class']) as found:

      self.assertTrue(
          self.get_only(found, 'ScalaWithJavaSources.class').endswith(
              'org/pantsbuild/testproject/javasources/ScalaWithJavaSources.class'))

      self.assertTrue(
          self.get_only(found, 'JavaSource.class').endswith(
              'org/pantsbuild/testproject/javasources/JavaSource.class'))

  def test_scalac_plugin_compile(self):
    with self.do_test_compile('testprojects/src/scala/org/pantsbuild/testproject/scalac/plugin',
                              expected_files=['HelloScalac.class', 'scalac-plugin.xml']) as found:

      self.assertTrue(
          self.get_only(found, 'HelloScalac.class').endswith(
              'org/pantsbuild/testproject/scalac/plugin/HelloScalac.class'))

      # Ensure that the plugin registration file is written to the root of the classpath.
      path = self.get_only(found, 'scalac-plugin.xml')
      self.assertTrue(path.endswith('/classes/scalac-plugin.xml'),
                      'plugin registration file `{}` not located at the '
                      'root of the classpath'.format(path))

      # And that it is well formed.
      root = ET.parse(path).getroot()
      self.assertEqual('plugin', root.tag)
      self.assertEqual('hello_scalac', root.find('name').text)
      self.assertEqual('org.pantsbuild.testproject.scalac.plugin.HelloScalac',
                       root.find('classname').text)

  def test_scalac_debug_symbol(self):
    with self.do_test_compile('testprojects/src/scala/org/pantsbuild/testproject/scalac/plugin',
                         expected_files=['HelloScalac.class', 'scalac-plugin.xml'],
                         extra_args=['--compile-zinc-debug-symbols']) as found:
      pass

  def test_zinc_unsupported_option(self):
    with self.temporary_workdir() as workdir:
      with self.temporary_cachedir() as cachedir:
        # compile with an unsupported flag
        pants_run = self.run_test_compile(
            workdir,
            cachedir,
            'testprojects/src/scala/org/pantsbuild/testproject/emptyscala',
            extra_args=[
              '--compile-zinc-args=-recompile-all-fraction',
              '--compile-zinc-args=0.5',
            ])
        self.assert_success(pants_run)

        # Confirm that we were warned.
        self.assertIn('is not supported, and is subject to change/removal', pants_run.stdout_data)

  def test_analysis_portability(self):
    target = 'testprojects/src/scala/org/pantsbuild/testproject/javasources'
    analysis_file_name = 'testprojects.src.scala.org.pantsbuild.testproject.javasources.javasources.analysis.portable'

    # do_new_project_compile_and_return_analysis executes pants with different build root/work directory each time.
    def do_new_project_compilation_and_return_analysis():
      with self.do_test_compile(target, iterations=1, expected_files=[analysis_file_name],
                                workdir_outside_of_buildroot=True) as found:
        files = found[analysis_file_name]
        self.assertEqual(1, len(files))
        with open(list(files)[0]) as file:
          return file.read()

    analysis1 = do_new_project_compilation_and_return_analysis()
    analysis2 = do_new_project_compilation_and_return_analysis()

    def extract_content(analysis):
      # TODO(stuhood): Comparing content before stamps only, because there is different line in internal apis section.
      # return re.sub(re.compile('lastModified\(\d+\)'), "lastModified()", analysis).split('\n')
      return analysis.partition("stamps")[0].split("\n")

    self.assertListEqual(extract_content(analysis1), extract_content(analysis2))

  def test_zinc_fatal_warning(self):
    def test_combination(target, default_fatal_warnings, expect_success, extra_args=[]):
      with self.temporary_workdir() as workdir:
        with self.temporary_cachedir() as cachedir:
          if default_fatal_warnings:
            arg = '--scala-platform-fatal-warnings'
          else:
            arg = '--no-scala-platform-fatal-warnings'
          pants_run = self.run_test_compile(
              workdir,
              cachedir,
              'testprojects/src/scala/org/pantsbuild/testproject/compilation_warnings:{}'.format(target),
              extra_args=[arg] + extra_args)

          if expect_success:
            self.assert_success(pants_run)
          else:
            self.assert_failure(pants_run)
    test_combination('defaultfatal', default_fatal_warnings=True, expect_success=False)
    test_combination('defaultfatal', default_fatal_warnings=False, expect_success=True)
    test_combination('fatal', default_fatal_warnings=True, expect_success=False)
    test_combination('fatal', default_fatal_warnings=False, expect_success=False)
    test_combination('nonfatal', default_fatal_warnings=True, expect_success=True)
    test_combination('nonfatal', default_fatal_warnings=False, expect_success=True)

    test_combination('fatal', default_fatal_warnings=True, expect_success=True,
      extra_args=['--compile-zinc-fatal-warnings-enabled-args=[\'-C-Werror\']'])
    test_combination('fatal', default_fatal_warnings=False, expect_success=False,
      extra_args=['--compile-zinc-fatal-warnings-disabled-args=[\'-S-Xfatal-warnings\']'])

  def test_pool_created_for_fresh_compile_but_not_for_valid_compile(self):
    with self.temporary_cachedir() as cachedir, self.temporary_workdir() as workdir:
      # Populate the workdir.
      first_run = self.run_test_compile(workdir, cachedir,
                            'testprojects/src/scala/org/pantsbuild/testproject/javasources')

      self.assertIn('isolation-zinc-pool-bootstrap', first_run.stdout_data)

      # Run valid compile.
      second_run = self.run_test_compile(workdir, cachedir,
                            'testprojects/src/scala/org/pantsbuild/testproject/javasources')

      self.assertNotIn('isolation-zinc-pool-bootstrap', second_run.stdout_data)
