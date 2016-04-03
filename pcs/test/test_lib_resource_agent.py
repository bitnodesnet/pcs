from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
import os.path

from lxml import etree

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs.test.tools.pcs_mock import mock
from pcs.test.tools.xml import XmlManipulation as XmlMan


from pcs import settings
from pcs.lib import error_codes
from pcs.lib import resource_agent as lib_ra
from pcs.lib.errors import ReportItemSeverity as Severities
from pcs.lib.external import CommandRunner


class LibraryResourceTest(TestCase):
    pass


class GetParameterTest(LibraryResourceTest):
    def test_with_all_data(self):
        xml = """
            <parameter name="test_param" required="1">
                <longdesc>
                    Long description
                </longdesc>
                <shortdesc>short description</shortdesc>
                <content type="test_type" default="default_value" />
            </parameter>
        """
        self.assertEqual(
            {
                "name": "test_param",
                "longdesc": "Long description",
                "shortdesc": "short description",
                "type": "test_type",
                "required": True,
                "default": "default_value"
            },
            lib_ra._get_parameter(etree.XML(xml))
        )

    def test_minimal_data(self):
        xml = '<parameter name="test_param" />'
        self.assertEqual(
            {
                "name": "test_param",
                "longdesc": "",
                "shortdesc": "",
                "type": "string",
                "required": False,
                "default": None
            },
            lib_ra._get_parameter(etree.XML(xml))
        )

    def test_no_name(self):
        xml = '<parameter />'
        assert_raise_library_error(
            lambda: lib_ra._get_parameter(etree.XML(xml)),
            (
                Severities.ERROR,
                error_codes.INVALID_METADATA_FORMAT,
                {}
            )
        )

    def test_invalid_element(self):
        xml = """
            <param name="test_param" required="1">
                <longdesc>
                    Long description
                </longdesc>
                <shortdesc>short description</shortdesc>
                <content type="test_type" default="default_value" />
            </param>
        """
        assert_raise_library_error(
            lambda: lib_ra._get_parameter(etree.XML(xml)),
            (
                Severities.ERROR,
                error_codes.INVALID_METADATA_FORMAT,
                {}
            )
        )


class GetAgentParametersTest(LibraryResourceTest):
    def test_all_data(self):
        xml = """
            <resource-agent>
                <parameters>
                    <parameter name="test_param" required="1">
                        <longdesc>
                            Long description
                        </longdesc>
                        <shortdesc>short description</shortdesc>
                        <content type="test_type" default="default_value" />
                    </parameter>
                    <parameter name="another parameter"/>
                </parameters>
            </resource-agent>
        """
        self.assertEqual(
            [
                {
                    "name": "test_param",
                    "longdesc": "Long description",
                    "shortdesc": "short description",
                    "type": "test_type",
                    "required": True,
                    "default": "default_value"
                },
                {
                    "name": "another parameter",
                    "longdesc": "",
                    "shortdesc": "",
                    "type": "string",
                    "required": False,
                    "default": None
                }
            ],
            lib_ra._get_agent_parameters(etree.XML(xml))
        )

    def test_empty_parameters(self):
        xml = """
            <resource-agent>
                <parameters />
            </resource-agent>
        """
        self.assertEqual(0, len(lib_ra._get_agent_parameters(etree.XML(xml))))

    def test_no_parameters(self):
        xml = """
            <resource-agent>
                <longdesc />
            </resource-agent>
        """
        self.assertEqual(0, len(lib_ra._get_agent_parameters(etree.XML(xml))))

    def test_invalid_format(self):
        xml = """
            <resource-agent>
                <parameters>
                    <parameter />
                </parameters>
            </resource-agent>
        """
        assert_raise_library_error(
            lambda: lib_ra._get_agent_parameters(etree.XML(xml)),
            (
                Severities.ERROR,
                error_codes.INVALID_METADATA_FORMAT,
                {}
            )
        )


class GetFenceAgentMetadataTest(LibraryResourceTest):
    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_invalid_agent_name(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_obj.return_value = True
        agent_name = "agent"

        assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": agent_name}
            )
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_relative_path_name(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_obj.return_value = True
        agent_name = "fence_agent/../fence"

        assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": agent_name}
            )
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_not_runnable(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_obj.return_value = False
        agent_name = "fence_agent"

        assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": agent_name}
            )
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_execution_failed(self, mock_is_runnable):
        mock_is_runnable.return_value = True
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("", 1)
        agent_name = "fence_ipmi"

        assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": agent_name}
            )
        )

        script_path = os.path.join(settings.fence_agent_binaries, agent_name)
        mock_runner.run.assert_called_once_with(
            [script_path, "-o", "metadata"]
        )

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_invalid_xml(self, mock_is_runnable):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("not xml", 0)
        mock_is_runnable.return_value = True
        agent_name = "fence_ipmi"

        assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": agent_name}
            )
        )

        script_path = os.path.join(settings.fence_agent_binaries, agent_name)
        mock_runner.run.assert_called_once_with(
            [script_path, "-o", "metadata"]
        )

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_success(self, mock_is_runnable):
        agent_name = "fence_ipmi"
        xml = "<xml />"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (xml, 0)
        mock_is_runnable.return_value = True

        out_dom = lib_ra.get_fence_agent_metadata(mock_runner, agent_name)

        script_path = os.path.join(settings.fence_agent_binaries, agent_name)
        mock_runner.run.assert_called_once_with(
            [script_path, "-o", "metadata"]
        )
        assert_xml_equal(xml, str(XmlMan(out_dom)))


class GetOcfResourceAgentMetadataTest(LibraryResourceTest):
    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_relative_path_provider(self, mock_is_runnable):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_is_runnable.return_value = True
        provider = "provider/../provider2"
        agent = "agent"

        assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": "ocf:{0}:{1}".format(provider, agent)}
            )
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_relative_path_agent(self, mock_is_runnable):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_is_runnable.return_value = True
        provider = "provider"
        agent = "agent/../agent2"

        assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": "ocf:{0}:{1}".format(provider, agent)}
            )
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_not_runnable(self, mock_is_runnable):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_is_runnable.return_value = False
        provider = "provider"
        agent = "agent"

        assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": "ocf:{0}:{1}".format(provider, agent)}
            )
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_execution_failed(self, mock_is_runnable):
        provider = "provider"
        agent = "agent"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("", 1)
        mock_is_runnable.return_value = True

        assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": "ocf:{0}:{1}".format(provider, agent)}
            )
        )

        script_path = os.path.join(settings.ocf_resources, provider, agent)
        mock_runner.run.assert_called_once_with(
            [script_path, "meta-data"],
            env_extend={"OCF_ROOT": settings.ocf_root}
        )

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_invalid_xml(self, mock_is_runnable):
        provider = "provider"
        agent = "agent"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("not xml", 0)
        mock_is_runnable.return_value = True

        assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": "ocf:{0}:{1}".format(provider, agent)}
            )
        )

        script_path = os.path.join(settings.ocf_resources, provider, agent)
        mock_runner.run.assert_called_once_with(
            [script_path, "meta-data"],
            env_extend={"OCF_ROOT": settings.ocf_root}
        )

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_success(self, mock_is_runnable):
        provider = "provider"
        agent = "agent"
        xml = "<xml />"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (xml, 0)
        mock_is_runnable.return_value = True

        out_dom = lib_ra._get_ocf_resource_agent_metadata(
            mock_runner, provider, agent
        )

        script_path = os.path.join(settings.ocf_resources, provider, agent)
        mock_runner.run.assert_called_once_with(
            [script_path, "meta-data"],
            env_extend={"OCF_ROOT": settings.ocf_root}
        )
        assert_xml_equal(xml, str(XmlMan(out_dom)))


class GetNagiosResourceAgentMetadataTest(LibraryResourceTest):
    def test_relative_path_name(self):
        agent = "agent/../agent2"
        assert_raise_library_error(
            lambda: lib_ra._get_nagios_resource_agent_metadata(agent),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": "nagios:" + agent}
            )
        )

    @mock.patch("lxml.etree.parse")
    def test_file_opening_exception(self, mock_obj):
        agent = "agent"
        mock_obj.side_effect = IOError()
        assert_raise_library_error(
            lambda: lib_ra._get_nagios_resource_agent_metadata(agent),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": "nagios:" + agent}
            )
        )

    @mock.patch("lxml.etree.parse")
    def test_invalid_xml(self, mock_obj):
        agent = "agent"
        mock_obj.side_effect = etree.XMLSyntaxError(None, None, None, None)
        assert_raise_library_error(
            lambda: lib_ra._get_nagios_resource_agent_metadata(agent),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": "nagios:" + agent}
            )
        )

    @mock.patch("lxml.etree.parse")
    def test_success(self, mock_obj):
        agent = "agent"
        xml = "<xml />"
        mock_obj.return_value = etree.ElementTree(etree.XML(xml))
        out_dom = lib_ra._get_nagios_resource_agent_metadata(agent)
        metadata_path = os.path.join(
            settings.nagios_metadata_path, agent + ".xml"
        )

        mock_obj.assert_called_once_with(metadata_path)
        assert_xml_equal(xml, str(XmlMan(out_dom)))


class GetAgentDescTest(LibraryResourceTest):
    def test_invalid_metadata_format(self):
        xml = "<xml />"
        assert_raise_library_error(
            lambda: lib_ra.get_agent_desc(etree.XML(xml)),
            (
                Severities.ERROR,
                error_codes.INVALID_METADATA_FORMAT,
                {}
            )
        )

    def test_no_desc(self):
        xml = "<resource-agent />"
        expected = {
            "longdesc": "",
            "shortdesc": ""
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_shortdesc_attribute(self):
        xml = '<resource-agent shortdesc="short description" />'
        expected = {
            "longdesc": "",
            "shortdesc": "short description"
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_shortdesc_element(self):
        xml = """
            <resource-agent>
                <shortdesc>short description</shortdesc>
            </resource-agent>
        """
        expected = {
            "longdesc": "",
            "shortdesc": "short description"
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_longdesc(self):
        xml = """
            <resource-agent>
                <longdesc>long description</longdesc>
            </resource-agent>
        """
        expected = {
            "longdesc": "long description",
            "shortdesc": ""
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_longdesc_and_shortdesc_attribute(self):
        xml = """
            <resource-agent shortdesc="short_desc">
                <longdesc>long description</longdesc>
            </resource-agent>
        """
        expected = {
            "longdesc": "long description",
            "shortdesc": "short_desc"
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_longdesc_and_shortdesc_element(self):
        xml = """
            <resource-agent>
                <shortdesc>short_desc</shortdesc>
                <longdesc>long description</longdesc>
            </resource-agent>
        """
        expected = {
            "longdesc": "long description",
            "shortdesc": "short_desc"
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))


class FilterFenceAgentParametersTest(LibraryResourceTest):
    def test_filter(self):
        params = [
            {"name": "debug"},
            {"name": "valid_param"},
            {"name": "verbose"},
            {"name": "help"},
            {"name": "action"},
            {"name": "another_param"},
            {"name": "version"},
        ]
        self.assertEqual(
            [
                {"name": "valid_param"},
                {"name": "another_param"}
            ],
            lib_ra._filter_fence_agent_parameters(params)
        )


class GetResourceAgentMetadata(LibraryResourceTest):
    def test_unsupported_class(self):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        agent = "class:provider:agent"

        assert_raise_library_error(
            lambda: lib_ra.get_resource_agent_metadata(mock_runner, agent),
            (
                Severities.ERROR,
                error_codes.UNSUPPORTED_RESOURCE_AGENT,
                {}
            )
        )

        mock_runner.run.assert_not_called()

    def test_ocf_no_provider(self):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        agent = "ocf:agent"

        assert_raise_library_error(
            lambda: lib_ra.get_resource_agent_metadata(mock_runner, agent),
            (
                Severities.ERROR,
                error_codes.UNSUPPORTED_RESOURCE_AGENT,
                {}
            )
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent._get_ocf_resource_agent_metadata")
    def test_ocf_ok(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        agent = "ocf:provider:agent"

        lib_ra.get_resource_agent_metadata(mock_runner, agent)

        mock_obj.assert_called_once_with(mock_runner, "provider", "agent")

    @mock.patch("pcs.lib.resource_agent._get_nagios_resource_agent_metadata")
    def test_nagios_ok(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        agent = "nagios:agent"

        lib_ra.get_resource_agent_metadata(mock_runner, agent)

        mock_obj.assert_called_once_with("agent")
        mock_runner.run.assert_not_called()
