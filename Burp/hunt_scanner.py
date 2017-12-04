import json
import os
import re
import urllib2
import urlparse
from lib.issue_listener import IssueListener
from lib.link_listener import LinkListener
from lib.message_controller import MessageController
from lib.scanner_issue import ScannerIssue
from lib.scanner_table_listener import ScannerTableListener
from lib.scanner_table_model import ScannerTableModel
from lib.settings_action import SettingsAction
from lib.tsl import TSL
from burp import IBurpExtender
from burp import IContextMenuFactory
from burp import IExtensionStateListener
from burp import IScannerCheck
from burp import ITab
from burp import ITextEditor
from java.awt import Desktop
from java.awt import Dimension
from java.awt import EventQueue
from java.awt import FlowLayout
from java.awt import Component
from java.awt.event import MouseAdapter
from java.lang import Runnable
from java.lang import Object
from java.lang import Thread
from javax.swing import BorderFactory
from javax.swing import DefaultCellEditor
from javax.swing import GroupLayout
from javax.swing import JButton
from javax.swing import JCheckBox
from javax.swing import JEditorPane
from javax.swing import JList
from javax.swing import JMenuItem
from javax.swing import JPopupMenu
from javax.swing import JSplitPane
from javax.swing import JScrollPane
from javax.swing import JTable
from javax.swing import JTabbedPane
from javax.swing import JTextArea
from javax.swing import JTree
from javax.swing import JFrame
from javax.swing import JPanel
from javax.swing import JLabel
from javax.swing import JButton
from javax.swing import BoxLayout
from javax.swing import SwingUtilities
from javax.swing import SwingConstants
from javax.swing.tree import DefaultMutableTreeNode
from javax.swing.tree import TreeSelectionModel
from org.python.core.util import StringUtil

# Using the Runnable class for thread-safety with Swing
class Run(Runnable):
    def __init__(self, runner):
        self.runner = runner

    def run(self):
        self.runner()

# TODO: Move other classes to different files
class BurpExtender(IBurpExtender, IExtensionStateListener, IScannerCheck, ITab, ITextEditor):
    EXTENSION_NAME = "HUNT Scanner"

    # TODO: Figure out why this gets called twice
    def __init__(self):
        self.issues = Issues()
        self.view = View(self.issues)

    def registerExtenderCallbacks(self, callbacks):
        self.callbacks = callbacks
        self.view.set_callbacks(callbacks)
        self.helpers = callbacks.getHelpers()
        self.view.set_helpers(self.helpers)
        self.callbacks.registerExtensionStateListener(self)
        self.callbacks.setExtensionName(self.EXTENSION_NAME)
        self.callbacks.addSuiteTab(self)
        self.callbacks.registerScannerCheck(self)

    def doPassiveScan(self, request_response):
        raw_request = request_response.getRequest()
        raw_response = request_response.getResponse()
        request = self.helpers.analyzeRequest(raw_request)
        response = self.helpers.analyzeResponse(raw_response)

        parameters = request.getParameters()
        vuln_parameters = self.issues.check_parameters(self.helpers, parameters)

        is_not_empty = len(vuln_parameters) > 0

        if is_not_empty:
            self.issues.create_scanner_issues(self.view, self.callbacks, self.helpers, vuln_parameters, request_response)

        # Do not show any Bugcrowd found issues in the Scanner window
        return []

    def getTabCaption(self):
        return self.EXTENSION_NAME

    def getUiComponent(self):
        return self.view.get_pane()

    def extensionUnloaded(self):
        print "HUNT Scanner plugin unloaded"
        return

class View:
    def __init__(self, issues):
        self.json = issues.get_json()
        self.issues_object = issues
        self.issues = issues.get_issues()
        self.scanner_issues = issues.get_scanner_issues()
        self.scanner_panes = {}
        self.scanner_table_models = {}
        self.scanner_tables = {}
        self.is_scanner_panes = []

        self.set_vuln_tree()
        self.set_tree()
        self.set_scanner_table_models()
        self.set_scanner_panes()
        self.set_pane()
        self.set_settings()
        self.set_tsl()

    def get_issues_object(self):
        return self.issues_object

    def set_callbacks(self, callbacks):
        self.callbacks = callbacks

    def set_helpers(self, helpers):
        self.helpers = helpers

    def get_helpers(self):
        return self.helpers

    def get_issues(self):
        return self.issues

    def get_scanner_issues(self):
        return self.scanner_issues

    def set_is_scanner_pane(self, scanner_pane):
        self.is_scanner_panes.append(scanner_pane)

    def get_is_scanner_pane(self, scanner_pane):
        for pane in self.get_is_scanner_panes():
            if pane == scanner_pane:
                return True

        return False

    def get_is_scanner_panes(self):
        return self.is_scanner_panes

    def set_vuln_tree(self):
        self.vuln_tree = DefaultMutableTreeNode("HUNT Scanner")

        vulns = self.json["issues"]

        # TODO: Sort the functionality by name and by vuln class
        for vuln_name in sorted(vulns):
            vuln = DefaultMutableTreeNode(vuln_name)
            self.vuln_tree.add(vuln)

            parameters = self.json["issues"][vuln_name]["params"]

            for parameter in sorted(parameters):
                param_node = DefaultMutableTreeNode(parameter)
                vuln.add(param_node)

        self.vuln_tree.add(DefaultMutableTreeNode("Settings"))

    # Creates a JTree object from the checklist
    def set_tree(self):
        self.tree = JTree(self.vuln_tree)
        self.tree.getSelectionModel().setSelectionMode(TreeSelectionModel.SINGLE_TREE_SELECTION)

    def get_tree(self):
        return self.tree

    def set_scanner_table_models(self):
        issues = self.issues

        for issue in issues:
            issue_name = issue["name"]
            issue_param = issue["param"]

            self.create_scanner_table_model(issue_name, issue_param)

    # Creates the tabs dynamically using data from the JSON file
    def set_scanner_panes(self):
        for issue in self.issues:
            issue_name = issue["name"]
            issue_param = issue["param"]
            key = issue_name + "." + issue_param

            top_pane = self.create_request_list_pane(issue_name)
            bottom_pane = self.create_tabbed_pane()

            scanner_pane = JSplitPane(JSplitPane.VERTICAL_SPLIT, top_pane, bottom_pane)
            self.scanner_panes[key] = scanner_pane

    def get_scanner_panes(self):
        return self.scanner_panes

    def create_request_list_pane(self, issue_name):
        request_list_pane = JScrollPane()

        return request_list_pane

    # Creates a JTabbedPane for each vulnerability per functionality
    def create_tabbed_pane(self):
        tabbed_pane = JTabbedPane()
        tabbed_pane.add("Advisory", JScrollPane())
        tabbed_pane.add("Request", JScrollPane())
        tabbed_pane.add("Response", JScrollPane())

        self.tabbed_pane = tabbed_pane

        return tabbed_pane

    def get_settings(self):
        return self.settings

    def set_settings(self):
        self.settings = JPanel()
        layout = GroupLayout(self.settings)
        self.settings.setLayout(layout)
        layout.setAutoCreateGaps(True)

        load_file_button = JButton("Load JSON File")
        load_file_button.setActionCommand("load")
        load_file_button.addActionListener(SettingsAction(self, load_file_button, None))
        save_file_button = JButton("Save JSON File")
        save_file_button.setActionCommand("save")
        save_file_button.addActionListener(SettingsAction(self, save_file_button, self.scanner_panes))

        horizontal_group1 = layout.createParallelGroup(GroupLayout.Alignment.LEADING)
        horizontal_group1.addComponent(load_file_button)
        horizontal_group1.addComponent(save_file_button)

        horizontal_group = layout.createSequentialGroup()
        horizontal_group.addGroup(horizontal_group1)

        layout.setHorizontalGroup(horizontal_group)

        vertical_group1 = layout.createParallelGroup(GroupLayout.Alignment.BASELINE)
        vertical_group1.addComponent(load_file_button)
        vertical_group2 = layout.createParallelGroup(GroupLayout.Alignment.BASELINE)
        vertical_group2.addComponent(save_file_button)

        vertical_group = layout.createSequentialGroup()
        vertical_group.addGroup(vertical_group1)
        vertical_group.addGroup(vertical_group2)

        layout.setVerticalGroup(vertical_group)

    def set_tsl(self):
        tsl = TSL(self)
        self.tree.addTreeSelectionListener(tsl)

        return

    def set_pane(self):
        status = JTextArea()
        status.setLineWrap(True)
        status.setText("Nothing selected")
        self.status = status

        request_list_pane = JScrollPane()
        scanner_pane = JSplitPane(JSplitPane.VERTICAL_SPLIT, request_list_pane, self.tabbed_pane)
        self.pane = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, JScrollPane(self.tree), scanner_pane)
        self.pane.setDividerLocation(310)
        self.pane.getLeftComponent().setMinimumSize(Dimension(310, 300))

    def get_pane(self):
        return self.pane

    # TODO: Move all scanner table functions into its own ScannerTable class
    #       as well as ScannerTableModel for all scanner table model functions
    def create_scanner_table_model(self, issue_name, issue_param):
        key = issue_name + "." + issue_param
        is_model_exists = key in self.scanner_table_models

        if is_model_exists:
            return

        scanner_table_model = ScannerTableModel()
        scanner_table_model.addColumn("")
        scanner_table_model.addColumn("Parameter")
        scanner_table_model.addColumn("Host")
        scanner_table_model.addColumn("Path")
        scanner_table_model.addColumn("ID")

        self.scanner_table_models[key] = scanner_table_model

    def set_scanner_table_model(self, scanner_issue, issue_name, issue_param, vuln_param):
        key = issue_name + "." + vuln_param
        scanner_issue_id = str(scanner_issue.getRequestResponse()).split("@")[1]
        scanner_table_model = self.scanner_table_models[key]

        # Using the addRow() method requires that the data type being passed to be of type
        # Vector() or Object(). Passing a Python object of type list in addRow causes a type
        # conversion error of sorts which presents as an ArrayOutOfBoundsException. Therefore,
        # row is an instantiation of Object() to avoid this error.
        row = Object()
        row = [False, issue_param, scanner_issue.getHttpService().getHost(), scanner_issue.getPath(), scanner_issue_id]
        scanner_table_model.addRow(row)

        # Wait for ScannerTableModel to update as to not get an ArrayOutOfBoundsException.
        Thread.sleep(500)

        scanner_table_model.fireTableDataChanged()
        scanner_table_model.fireTableStructureChanged()

    def get_scanner_table_model(self, issue_name, issue_param):
        key = issue_name + "." + issue_param
        return self.scanner_table_models[key]

    def set_scanner_pane(self, scanner_pane, issue_name, issue_param):
        key = issue_name + "." + issue_param
        request_table_pane = scanner_pane.getTopComponent()

        if key in self.scanner_tables:
            scanner_table = self.scanner_tables[key]
        else:
            scanner_table = self.create_scanner_table(scanner_pane, issue_name, issue_param)
            self.scanner_tables[key] = scanner_table

        request_table_pane.getViewport().setView(scanner_table)
        request_table_pane.revalidate()
        request_table_pane.repaint()

    def create_scanner_table(self, scanner_pane, issue_name, issue_param):
        scanner_table_model = self.get_scanner_table_model(issue_name, issue_param)

        scanner_table = JTable(scanner_table_model)
        scanner_table.getColumnModel().getColumn(0).setMaxWidth(10)
        scanner_table.putClientProperty("terminateEditOnFocusLost", True)
        scanner_table_listener = ScannerTableListener(self, scanner_table, issue_name, issue_param)
        scanner_table_model.addTableModelListener(scanner_table_listener)
        scanner_table_list_listener = IssueListener(self, scanner_table, scanner_pane, issue_name, issue_param)
        scanner_table.getSelectionModel().addListSelectionListener(scanner_table_list_listener)

        return scanner_table

    # Takes into account if there are more than one scanner issues that share the same hostname, path, name, param, and id
    def set_tabbed_pane(self, scanner_pane, request_list, issue_hostname, issue_path, issue_name, issue_param, scanner_issue_id):
        tabbed_pane = scanner_pane.getBottomComponent()
        scanner_issues = self.get_scanner_issues()
        current_issue = self.set_current_issue(scanner_issues, issue_hostname, issue_path, issue_name, issue_param, scanner_issue_id)

        advisory_tab_pane = self.set_advisory_tab_pane(current_issue)
        tabbed_pane.setComponentAt(0, advisory_tab_pane)

        request_tab_pane = self.set_request_tab_pane(current_issue)
        tabbed_pane.setComponentAt(1, request_tab_pane)

        response_tab_pane = self.set_response_tab_pane(current_issue)
        tabbed_pane.setComponentAt(2, response_tab_pane)

    def set_current_issue(self, scanner_issues, issue_hostname, issue_path, issue_name, issue_param, scanner_issue_id):
        for scanner_issue in scanner_issues:
            is_same_hostname = scanner_issue.getHostname() == issue_hostname
            is_same_path = scanner_issue.getPath() == issue_path
            is_same_name = scanner_issue.getIssueName() == issue_name
            is_same_param = scanner_issue.getParameter() == issue_param
            is_same_id = str(scanner_issue.getRequestResponse()).split("@")[1] == scanner_issue_id
            is_same_issue = is_same_hostname and is_same_path and is_same_name and is_same_param and is_same_id

            if is_same_issue:
                return scanner_issue

    def set_advisory_tab_pane(self, scanner_issue):
        advisory_pane = JEditorPane()
        advisory_pane.setEditable(False)
        advisory_pane.setEnabled(True)
        advisory_pane.setContentType("text/html")
        link_listener = LinkListener()
        advisory_pane.addHyperlinkListener(link_listener)
        advisory = "<html><b>Location</b>: {}<br><br>{}</html>"
        advisory_pane.setText(advisory.format(scanner_issue.getUrl().encode("utf-8"), scanner_issue.getIssueDetail()))

        return JScrollPane(advisory_pane)

    def set_request_tab_pane(self, scanner_issue):
        request_response = scanner_issue.getRequestResponse()
        controller = MessageController(request_response)
        message_editor = self.callbacks.createMessageEditor(controller, True)
        message_editor.setMessage(request_response.getRequest(), True)
        component = message_editor.getComponent()

        return component

    def set_response_tab_pane(self, scanner_issue):
        request_response = scanner_issue.getRequestResponse()
        controller = MessageController(request_response)
        message_editor = self.callbacks.createMessageEditor(controller, True)
        message_editor.setMessage(request_response.getResponse(), False)
        component = message_editor.getComponent()

        return component

    def traverse_tree(self, tree, model, issue_name, issue_param, issue_count, total_count):
        root = model.getRoot()
        count = int(root.getChildCount())
        traverse = {}

        for i in range(count):
            node = model.getChild(root, i)
            traverse["node"] = node
            tree_issue_name = node.toString()

            is_issue_name = re.search(issue_name, tree_issue_name)

            if is_issue_name:
                child_count = node.getChildCount()

                for j in range(child_count):
                    child = node.getChildAt(j)
                    traverse["child"] = child
                    tree_param_name = child.toString()

                    is_param_name = re.search(issue_param, tree_param_name)

                    if is_param_name:
                        traverse["param_text"] = issue_param + " (" + str(issue_count) + ")"
                        break

                traverse["issue_text"] = issue_name + " (" + str(total_count) + ")"
                break

        return traverse

    def set_scanner_count(self, issue_name, issue_param, issue_count, total_count):
        tree = self.get_tree()
        model = tree.getModel()
        traverse = self.traverse_tree(tree, model, issue_name, issue_param, issue_count, total_count)
        node = traverse["node"]
        child = traverse["child"]

        child.setUserObject(traverse["param_text"])
        model.nodeChanged(child)
        model.reload(node)

        node.setUserObject(traverse["issue_text"])
        model.nodeChanged(node)
        model.reload(node)

class Issues:
    scanner_issues = []
    total_count = {}
    issues_count = {}

    def __init__(self):
        self.set_json()
        self.set_issues()

    def set_json(self):
        data_file = os.getcwd() + os.sep + "conf" + os.sep + "issues.json"

        try:
            with open(data_file) as data:
                self.json = json.load(data)
        except IssuesFileLoadingError as e:
            print e

    def get_json(self):
        return self.json

    def set_issues(self):
        self.issues = []
        issues = self.json["issues"]

        for issue_name in issues:
            parameters = issues[issue_name]["params"]

            for parameter in parameters:
                issue = {
                    "name": issue_name.encode("utf-8").strip(),
                    "param": parameter.encode("utf-8").strip(),
                    "count": 0
                }

                self.issues.append(issue)

    def get_issues(self):
        return self.issues

    def set_scanner_issues(self, scanner_issue):
        self.scanner_issues.append(scanner_issue)

    def get_scanner_issues(self):
        return self.scanner_issues

    def check_parameters(self, helpers, parameters):
        vuln_params = []

        for parameter in parameters:
            # Make sure that the parameter is not from the cookies
            # https://portswigger.net/burp/extender/api/constant-values.html#burp.IParameter
            is_not_cookie = parameter.getType() != 2

            if is_not_cookie:
                # Handle double URL encoding just in case
                parameter_decoded = helpers.urlDecode(parameter.getName())
                parameter_decoded = helpers.urlDecode(parameter_decoded)

                self.check_vuln_params(vuln_params, parameter_decoded, parameter)

        return vuln_params

    def check_vuln_params(self, vuln_params, parameter_decoded, parameter):
        for issue in self.issues:
            vuln_name = issue["name"]
            vuln_param = issue["param"]
            is_vuln_found = re.search(vuln_param, parameter_decoded, re.IGNORECASE)

            if is_vuln_found:
                self.vuln_param_add(vuln_params, vuln_name, vuln_param, parameter_decoded, parameter)
                #self.vuln_param_found(vuln_params, vuln_name, vuln_param, parameter_decoded, parameter)
            else:
                continue

    def vuln_param_found(self, vuln_params, vuln_name, vuln_param, parameter_decoded, parameter):
        is_same_vuln_name = vuln_param == parameter_decoded

        if is_same_vuln_name:
            self.vuln_param_add(vuln_params, vuln_name, vuln_param, parameter_decoded, parameter)
        else:
            self.vuln_param_lookup(vuln_params, vuln_name, vuln_param, parameter_decoded, parameter)

    def vuln_param_lookup(self, vuln_params, vuln_name, vuln_param, parameter_decoded, parameter):
        # Put try catch
        url = "http://api.pearson.com/v2/dictionaries/ldoce5/entries?headword=" + parameter_decoded
        response = urllib2.urlopen(url)

        # Wait a second for response to come back
        Thread.sleep(1000)

        data = json.load(response)

        # Checks an English dictionary if parameter is a real word. If it isn't, add it.
        # Catches: id_param, param_id, paramID, etc.
        # Does not catch: idea, ideology, identify, etc.
        is_real_word = int(data["count"]) > 0

        if not is_real_word:
            self.vuln_param_add(vuln_params, vuln_name, vuln_param, parameter_decoded, parameter.getValue())

    def vuln_param_add(self, vuln_params, vuln_name, vuln_param, param, value):
        vuln_params.append({
            "vuln_name": vuln_name,
            "vuln_param": vuln_param,
            "param": param,
            "value": value
        })

    def create_scanner_issues(self, view, callbacks, helpers, vuln_parameters, request_response):
        issues = self.issues
        json = self.json

        # Takes into account if there is more than one vulnerable parameter
        for vuln_parameter in vuln_parameters:
            issue_name = vuln_parameter["vuln_name"]
            vuln_param = vuln_parameter["vuln_param"]
            param_name = vuln_parameter["param"]
            param_value = vuln_parameter["value"]

            url = helpers.analyzeRequest(request_response).getUrl()
            url = urlparse.urlsplit(str(url))
            hostname = url.hostname
            path = url.path
            url = url.scheme + "://" + url.hostname + url.path

            http_service = request_response.getHttpService()
            http_messages = [callbacks.applyMarkers(request_response, None, None)]
            detail = json["issues"][issue_name]["detail"]
            severity = "Medium"

            scanner_issue = ScannerIssue(url, issue_name, param_name, vuln_param, param_value, hostname, path, http_service, http_messages, detail, severity, request_response)
            is_scanner_issue_dupe = self.check_duplicate_issue(scanner_issue)

            if is_scanner_issue_dupe:
                continue
            else:
                self.set_scanner_issues(scanner_issue)

            issue_count = self.set_issue_count(issue_name, vuln_param)
            total_count = self.total_count[issue_name]

            view.set_scanner_count(issue_name, vuln_param, issue_count, total_count)
            view.set_scanner_table_model(scanner_issue, issue_name, param_name, vuln_param)

    def check_duplicate_issue(self, scanner_issue_local):
        scanner_issues = self.get_scanner_issues()

        for scanner_issue in scanner_issues:
            is_same_issue_name = scanner_issue_local.getIssueName() == scanner_issue.getIssueName()
            is_same_parameter = scanner_issue_local.getParameter() == scanner_issue.getParameter()
            is_same_vuln_parameter = scanner_issue_local.getVulnParameter() == scanner_issue.getVulnParameter()
            is_same_hostname = scanner_issue_local.getHostname() == scanner_issue.getHostname()
            is_same_path = scanner_issue_local.getPath() == scanner_issue.getPath()
            is_dupe = is_same_issue_name and is_same_parameter and is_same_vuln_parameter

            if is_dupe:
                return True

        return False

    def set_issue_count(self, issue_name, issue_param):
        for issue in self.issues:
            is_name = issue["name"] == issue_name
            is_param = issue["param"] == issue_param
            is_issue = is_name and is_param

            if is_issue:
                issue["count"] += 1
                is_total_key_exists = issue_name in self.total_count

                if is_total_key_exists:
                    self.total_count[issue_name] += 1
                else:
                    self.total_count[issue_name] = 1

                key = issue_name + "." + issue_param
                is_issue_key_exists = key in self.issues_count

                if is_issue_key_exists:
                    self.issues_count[key] += 1
                else:
                    self.issues_count[key] = 1

                return issue["count"]

    def get_issues_count(self, issue_name, issue_param):
        key = issue_name + "." + issue_param
        return self.issues_count[key]

    def change_issues_count(self, issue_name, issue_param, is_checked):
        key = issue_name + "." + issue_param

        if is_checked:
            self.issues_count[key] -= 1
        else:
            self.issues_count[key] += 1

    def get_total_count(self, issue_name):
        return self.total_count[issue_name]

    def change_total_count(self, issue_name, is_checked):
        if is_checked:
            self.total_count[issue_name] -= 1
        else:
            self.total_count[issue_name] += 1


if __name__ in ('__main__', 'main'):
    EventQueue.invokeLater(Run(BurpExtender))
