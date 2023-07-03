import pytest

from baselines.url_parser import *

# code adopted from files in https://github.com/librariesio/librariesio-url-parser/tree/main/spec


class TestAndroidGooglesourceUrlParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://android.googlesource.com/platform/prebuilts/tools",
                "platform/prebuilts/tools",
            ),
            (
                "https://android.googlesource.com/platform/prebuilts/tools#anchor?p=some_param",
                "platform/prebuilts/tools",
            ),
            (
                "https://android.googlesource.com/device/amlogic/yukawa/+/refs/heads/master",
                "device/amlogic/yukawa",
            ),
        ],
    )
    def test_parse(self, url: str, full_name: str):
        assert AndroidGooglesourceUrlParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://android.googlesource.com/platform/prebuilts/tools",
                "https://android.googlesource.com/platform/prebuilts/tools",
            ),
            (
                "https://android.googlesource.com/platform/prebuilts/tools#anchor?p=some_param",
                "https://android.googlesource.com/platform/prebuilts/tools",
            ),
            (
                "https://android.googlesource.com/device/amlogic/yukawa/+/refs/tags/android-12.1.0_r16",
                "https://android.googlesource.com/device/amlogic/yukawa",
            ),
        ],
    )
    def test_parse_to_full_url(self, url: str, full_name: str):
        assert AndroidGooglesourceUrlParser.parse_to_full_url(url) == full_name

    def test_case_sensitive(self):
        assert AndroidGooglesourceUrlParser.CASE_SENSITIVE == True


class TestApacheGitWipUrlParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            ("https://git-wip-us.apache.org/repos/asf?p=nifi.git", "nifi"),
            (
                "https://git-wip-us.apache.org/repos/asf?p=flume.git;a=tree;h=refs/heads/trunk;hb=trunk",
                "flume",
            ),
        ],
    )
    def test_parse(self, url: str, full_name: str):
        assert ApacheGitWipUrlParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://git-wip-us.apache.org/repos/asf?p=nifi.git",
                "https://git-wip-us.apache.org/repos/asf/nifi",
            ),
            (
                "https://git-wip-us.apache.org/repos/asf?p=flume.git;a=tree;h=refs/heads/trunk;hb=trunk",
                "https://git-wip-us.apache.org/repos/asf/flume",
            ),
        ],
    )
    def test_parse_to_full_url(self, url: str, full_name: str):
        assert ApacheGitWipUrlParser.parse_to_full_url(url) == full_name

    def test_case_sensitive(self):
        assert ApacheGitWipUrlParser.CASE_SENSITIVE == True


class TestApacheGitboxUrlParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://gitbox.apache.org/repos/asf?p=camel-quarkus.git;a=summary",
                "camel-quarkus",
            ),
            ("https://gitbox.apache.org/repos/asf/metamodel.git", "metamodel"),
            (
                "https://gitbox.apache.org/repos/asf?p=sling-org-apache-sling-testing-resourceresolver-mock.git",
                "sling-org-apache-sling-testing-resourceresolver-mock",
            ),
            (
                "https://gitbox.apache.org/repos/asf?p=lucene-solr.git;f=lucene",
                "lucene-solr",
            ),
        ],
    )
    def test_parse(self, url: str, full_name: str):
        assert ApacheGitboxUrlParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://gitbox.apache.org/repos/asf?p=camel-quarkus.git;a=summary",
                "https://gitbox.apache.org/repos/asf/camel-quarkus",
            ),
            (
                "https://gitbox.apache.org/repos/asf/metamodel.git",
                "https://gitbox.apache.org/repos/asf/metamodel",
            ),
        ],
    )
    def test_parse_to_full_url(self, url: str, full_name: str):
        assert ApacheGitboxUrlParser.parse_to_full_url(url) == full_name

    def test_case_sensitive(self):
        assert ApacheGitboxUrlParser.CASE_SENSITIVE == True


class TestApacheSvnUrlParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "http://svn.apache.org/viewvc/stanbol/tags/apache-stanbol-1.0.0/",
                "stanbol",
            ),
            (
                "http://svn.apache.org/viewvc/maven/pom/tags/apache-7",
                "maven/pom/tags/apache-7",
            ),
            (
                "http://svn.apache.org/viewvc/maven/pom/tags/apache-16/ignite-parent/ignite-zookeeper",
                "maven/pom/tags/apache-16",
            ),
            (
                "http://svn.apache.org/viewcvs.cgi/portals/pluto/tags/pluto-1.1.7",
                "portals/pluto",
            ),
            (
                "scm:svn:https://svn.apache.org/repos/asf/stanbol/tags/apache-stanbol-1.0.0/release-1.0.0-branch/stanbol.apache.org",
                "stanbol",
            ),
            (
                "https://svn.apache.org/repos/asf/maven/wagon/tags/wagon-1.0-beta-2",
                "maven/wagon",
            ),
        ],
    )
    def test_parse(self, url: str, full_name: str):
        assert ApacheSvnUrlParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://svn.apache.org/viewvc/stanbol/tags/apache-stanbol-1.0.0/",
                "https://svn.apache.org/viewvc/stanbol",
            ),
            (
                "http://svn.apache.org/viewvc/maven/pom/tags/apache-7",
                "https://svn.apache.org/viewvc/maven/pom/tags/apache-7",
            ),
            (
                "http://svn.apache.org/viewvc/maven/pom/tags/apache-16/ignite-parent/ignite-zookeeper",
                "https://svn.apache.org/viewvc/maven/pom/tags/apache-16",
            ),
        ],
    )
    def test_parse_to_full_url(self, url: str, full_name: str):
        assert ApacheSvnUrlParser.parse_to_full_url(url) == full_name

    def test_case_sensitive(self):
        assert ApacheSvnUrlParser.CASE_SENSITIVE == True


class TestBitbucketURLParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            ("https://bitbucket.com/maxcdn/shml/", "maxcdn/shml"),
            ("https://foo.bitbucket.org/bar", "foo/bar"),
            (
                "git+https://bitbucket.com/hugojosefson/express-cluster-stability.git",
                "hugojosefson/express-cluster-stability",
            ),
            ("sughodke.bitbucket.com/linky.js/", "sughodke/linky.js"),
            ("www.bitbucket.com/37point2/brainfuckifyjs", "37point2/brainfuckifyjs"),
            (
                "ssh://git@bitbucket.org:brozeph/node-craigslist.git",
                "brozeph/node-craigslist",
            ),
            (
                "ssh+git@bitbucket.com:omardelarosa/tonka-npm.git",
                "omardelarosa/tonka-npm",
            ),
            (
                "scm:svn:https://bitbucket.com/tanhaichao/top4j/tags/top4j-0.0.1",
                "tanhaichao/top4j",
            ),
            (
                "scm:${project.scm.vendor}:git@bitbucket.com:adamcin/maven-s3-wagon.git",
                "adamcin/maven-s3-wagon",
            ),
            ("scm:https://vert-x@bitbucket.com/purplefox/vert.x", "purplefox/vert.x"),
            ("scm:https:https://bitbucket.com/vaadin/vaadin.git", "vaadin/vaadin"),
            (
                "scm:https://bitbucket.com/daimajia/AndroidAnimations.git",
                "daimajia/AndroidAnimations",
            ),
            ("scm:http:http://NICTA@bitbucket.com/NICTA/scoobi.git", "NICTA/scoobi"),
            (
                "scm:http:http://etorreborre@bitbucket.com/etorreborre/specs.git",
                "etorreborre/specs",
            ),
            (
                "scm:hg:https://bitbucket.com/wangenyong/EnAndroidLibrary",
                "wangenyong/EnAndroidLibrary",
            ),
            ("scm:hg:git://bitbucket.com/jesselong/muffero.git", "jesselong/muffero"),
            (
                "scm:git:ssh@bitbucket.com:claudius108/maven-plugins.git",
                "claudius108/maven-plugins",
            ),
            (
                "scm:git|ssh://git@bitbucket.com/zinin/tomcat-redis-session.git",
                "zinin/tomcat-redis-session",
            ),
            (
                "scm:git:prasadpnair@bitbucket.com/Jamcracker/jit-core.git",
                "Jamcracker/jit-core",
            ),
            (
                "scm:git:scm:git:git://bitbucket.com/spring-projects/spring-integration.git",
                "spring-projects/spring-integration",
            ),
            ("scm:git:https://bitbucket.com/axet/sqlite4java", "axet/sqlite4java"),
            ("scm:git:https://bitbucket.com/celum/db-tool.git", "celum/db-tool"),
            (
                "scm:git:https://ffromm@bitbucket.com/jenkinsci/slave-setup-plugin.git",
                "jenkinsci/slave-setup-plugin",
            ),
            ("scm:git:bitbucket.com/yfcai/CREG.git", "yfcai/CREG"),
            (
                "scm:git@bitbucket.com:urunimi/PullToRefreshAndroid.git",
                "urunimi/PullToRefreshAndroid",
            ),
            ("scm:git:bitbucket.com/larsrh/libisabelle.git", "larsrh/libisabelle"),
            ("scm:git://bitbucket.com/lihaoyi/ajax.git", "lihaoyi/ajax"),
            (
                "scm:git@bitbucket.com:ExpediaInc/ean-android.git",
                "ExpediaInc/ean-android",
            ),
            (
                "https://RobinQu@bitbucket.com/RobinQu/node-gear.git",
                "RobinQu/node-gear",
            ),
            (
                "https://taylorhakes@bitbucket.com/taylorhakes/promise-polyfill.git",
                "taylorhakes/promise-polyfill",
            ),
            ("https://hcnode.bitbucket.com/node-gitignore", "hcnode/node-gitignore"),
            (
                "https://bitbucket.org/srcagency/js-slash-tail.git",
                "srcagency/js-slash-tail",
            ),
            ("https://gf3@bitbucket.com/gf3/IRC-js.git", "gf3/IRC-js"),
            (
                "https://crcn:KQ3Lc6za@bitbucket.com/crcn/verify.js.git",
                "crcn/verify.js",
            ),
            ("https://bgrins.bitbucket.com/spectrum", "bgrins/spectrum"),
            ("//bitbucket.com/dtrejo/report.git", "dtrejo/report"),
            (
                "=https://bitbucket.com/amansatija/Cus360MavenCentralDemoLib.git",
                "amansatija/Cus360MavenCentralDemoLib",
            ),
            ("git+https://bebraw@bitbucket.com/bebraw/colorjoe.git", "bebraw/colorjoe"),
            (
                "git:///bitbucket.com/NovaGL/homebridge-openremote.git",
                "NovaGL/homebridge-openremote",
            ),
            (
                "git://git@bitbucket.com/jballant/webpack-strip-block.git",
                "jballant/webpack-strip-block",
            ),
            (
                "git://bitbucket.com/2betop/yogurt-preprocessor-extlang.git",
                "2betop/yogurt-preprocessor-extlang",
            ),
            ("git:/git://bitbucket.com/antz29/node-twister.git", "antz29/node-twister"),
            (
                "git:/bitbucket.com/shibukawa/burrows-wheeler-transform.jsx.git",
                "shibukawa/burrows-wheeler-transform.jsx",
            ),
            (
                "git:git://bitbucket.com/alaz/mongo-scala-driver.git",
                "alaz/mongo-scala-driver",
            ),
            (
                "git:git@bitbucket.com:doug-martin/string-extended.git",
                "doug-martin/string-extended",
            ),
            (
                "git:bitbucket.com//dominictarr/level-couch-sync.git",
                "dominictarr/level-couch-sync",
            ),
            ("git:bitbucket.com/dominictarr/keep.git", "dominictarr/keep"),
            ("git:https://bitbucket.com/vaadin/cdi.git", "vaadin/cdi"),
            ("git@git@bitbucket.com:dead-horse/webT.git", "dead-horse/webT"),
            ("git@bitbucket.com:agilemd/then.git", "agilemd/then"),
            ("https : //bitbucket.com/alex101/texter.js.git", "alex101/texter.js"),
            ("git@git.bitbucket.com:daddye/stitchme.git", "daddye/stitchme"),
            (
                "bitbucket.com/1995hnagamin/hubot-achievements",
                "1995hnagamin/hubot-achievements",
            ),
            (
                "git//bitbucket.com/divyavanmahajan/jsforce_downloader.git",
                "divyavanmahajan/jsforce_downloader",
            ),
            (
                "scm:git:https://michaelkrog@bitbucket.com/michaelkrog/filter4j.git",
                "michaelkrog/filter4j",
            ),
        ],
    )
    def test_parse(self, url: str, full_name: str):
        assert BitbucketURLParser.parse(url) == full_name

    def test_handle_anchors(self):
        full_name = "michaelkrog/filter4j"
        url = (
            "scm:git:https://michaelkrog@bitbucket.com/michaelkrog/filter4j.git#anchor"
        )
        assert BitbucketURLParser.parse(url) == full_name

    def test_handle_querystrings(self):
        full_name = "michaelkrog/filter4j"
        url = "scm:git:https://michaelkrog@bitbucket.com/michaelkrog/filter4j.git?foo=bar&wut=wah"
        assert BitbucketURLParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "[scm:git:https://michaelkrog@bitbucket.com/michaelkrog/filter4j.git]",
                "michaelkrog/filter4j",
            ),
            (
                "<scm:git:https://michaelkrog@bitbucket.com/michaelkrog/filter4j.git>",
                "michaelkrog/filter4j",
            ),
            (
                "(scm:git:https://michaelkrog@bitbucket.com/michaelkrog/filter4j.git)",
                "michaelkrog/filter4j",
            ),
        ],
    )
    def test_handle_brackets(self, url: str, full_name: str):
        assert BitbucketURLParser.parse(url) == full_name

    @pytest.mark.parametrize(
        "url",
        [
            "https://google.com",
            "https://bitbucket.com/foo",
            "https://bitbucker.com",
            "https://foo.bitbucket.io",
            "https://bitbucket.ibm.com/apiconnect/apiconnect",
        ],
    )
    def test_parse_non_bitbucket_urls(self, url: str):
        assert BitbucketURLParser.parse(url) == None

    def test_case_sensitive(self):
        assert BitbucketURLParser.CASE_SENSITIVE == False


class TestDrupalUrlParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [("https://git.drupalcode.org/project/search_api_solr", "search_api_solr")],
    )
    def test_parse(self, url: str, full_name: str):
        assert DrupalUrlParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://git.drupalcode.org/project/search_api_solr",
                "https://git.drupalcode.org/project/search_api_solr",
            )
        ],
    )
    def test_parse_to_full_url(self, url: str, full_name: str):
        assert DrupalUrlParser.parse_to_full_url(url) == full_name

    def test_case_sensitive(self):
        assert DrupalUrlParser.CASE_SENSITIVE == False


class TestEclipseGitUrlParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://git.eclipse.org/c/dltk/org.eclipse.dltk.releng.git",
                "dltk/org.eclipse.dltk.releng.git",
            ),
            (
                "http://git.eclipse.org/c/jetty/org.eclipse.jetty.orbit.git/tree/jetty-orbit",
                "jetty/org.eclipse.jetty.orbit.git",
            ),
        ],
    )
    def test_parse(self, url: str, full_name: str):
        assert EclipseGitUrlParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://git.eclipse.org/c/dltk/org.eclipse.dltk.releng.git",
                "https://git.eclipse.org/c/dltk/org.eclipse.dltk.releng.git",
            ),
            (
                "http://git.eclipse.org/c/jetty/org.eclipse.jetty.orbit.git/tree/jetty-orbit",
                "https://git.eclipse.org/c/jetty/org.eclipse.jetty.orbit.git",
            ),
        ],
    )
    def test_parse_to_full_url(self, url: str, full_name: str):
        assert EclipseGitUrlParser.parse_to_full_url(url) == full_name

    def test_case_sensitive(self):
        assert EclipseGitUrlParser.CASE_SENSITIVE == True


class TestGithubURLParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            ("https://github.com/maxcdn/shml/", "maxcdn/shml"),
            ("https://foo.github.io/bar", "foo/bar"),
            (
                "git+https://github.com/hugojosefson/express-cluster-stability.git",
                "hugojosefson/express-cluster-stability",
            ),
            ("sughodke.github.com/linky.js/", "sughodke/linky.js"),
            ("www.github.com/37point2/brainfuckifyjs", "37point2/brainfuckifyjs"),
            (
                "ssh://git@github.org:brozeph/node-craigslist.git",
                "brozeph/node-craigslist",
            ),
            ("ssh+git@github.com:omardelarosa/tonka-npm.git", "omardelarosa/tonka-npm"),
            (
                "scm:svn:https://github.com/tanhaichao/top4j/tags/top4j-0.0.1",
                "tanhaichao/top4j",
            ),
            (
                "scm:${project.scm.vendor}:git@github.com:adamcin/maven-s3-wagon.git",
                "adamcin/maven-s3-wagon",
            ),
            ("scm:https://vert-x@github.com/purplefox/vert.x", "purplefox/vert.x"),
            ("scm:https:https://github.com/vaadin/vaadin.git", "vaadin/vaadin"),
            (
                "scm:https://github.com/daimajia/AndroidAnimations.git",
                "daimajia/AndroidAnimations",
            ),
            ("scm:http:http://NICTA@github.com/NICTA/scoobi.git", "NICTA/scoobi"),
            (
                "scm:http:http://etorreborre@github.com/etorreborre/specs.git",
                "etorreborre/specs",
            ),
            (
                "scm:hg:https://github.com/wangenyong/EnAndroidLibrary",
                "wangenyong/EnAndroidLibrary",
            ),
            ("scm:hg:git://github.com/jesselong/muffero.git", "jesselong/muffero"),
            (
                "scm:git:ssh@github.com:claudius108/maven-plugins.git",
                "claudius108/maven-plugins",
            ),
            (
                "scm:git|ssh://git@github.com/zinin/tomcat-redis-session.git",
                "zinin/tomcat-redis-session",
            ),
            (
                "scm:git:prasadpnair@github.com/Jamcracker/jit-core.git",
                "Jamcracker/jit-core",
            ),
            (
                "scm:git:scm:git:git://github.com/spring-projects/spring-integration.git",
                "spring-projects/spring-integration",
            ),
            ("scm:git:https://github.com/axet/sqlite4java", "axet/sqlite4java"),
            ("scm:git:https://github.com/celum/db-tool.git", "celum/db-tool"),
            (
                "scm:git:https://ffromm@github.com/jenkinsci/slave-setup-plugin.git",
                "jenkinsci/slave-setup-plugin",
            ),
            ("scm:git:github.com/yfcai/CREG.git", "yfcai/CREG"),
            (
                "scm:git@github.com:urunimi/PullToRefreshAndroid.git",
                "urunimi/PullToRefreshAndroid",
            ),
            ("scm:git:github.com/larsrh/libisabelle.git", "larsrh/libisabelle"),
            ("scm:git://github.com/lihaoyi/ajax.git", "lihaoyi/ajax"),
            ("scm:git@github.com:ExpediaInc/ean-android.git", "ExpediaInc/ean-android"),
            ("https://RobinQu@github.com/RobinQu/node-gear.git", "RobinQu/node-gear"),
            (
                "https://taylorhakes@github.com/taylorhakes/promise-polyfill.git",
                "taylorhakes/promise-polyfill",
            ),
            ("https://hcnode.github.com/node-gitignore", "hcnode/node-gitignore"),
            (
                "https://github.org/srcagency/js-slash-tail.git",
                "srcagency/js-slash-tail",
            ),
            ("https://gf3@github.com/gf3/IRC-js.git", "gf3/IRC-js"),
            ("https://crcn:KQ3Lc6za@github.com/crcn/verify.js.git", "crcn/verify.js"),
            ("https://bgrins.github.com/spectrum", "bgrins/spectrum"),
            ("//github.com/dtrejo/report.git", "dtrejo/report"),
            (
                "=https://github.com/amansatija/Cus360MavenCentralDemoLib.git",
                "amansatija/Cus360MavenCentralDemoLib",
            ),
            ("git+https://bebraw@github.com/bebraw/colorjoe.git", "bebraw/colorjoe"),
            (
                "git:///github.com/NovaGL/homebridge-openremote.git",
                "NovaGL/homebridge-openremote",
            ),
            (
                "git://git@github.com/jballant/webpack-strip-block.git",
                "jballant/webpack-strip-block",
            ),
            (
                "git://github.com/2betop/yogurt-preprocessor-extlang.git",
                "2betop/yogurt-preprocessor-extlang",
            ),
            ("git:/git://github.com/antz29/node-twister.git", "antz29/node-twister"),
            (
                "git:/github.com/shibukawa/burrows-wheeler-transform.jsx.git",
                "shibukawa/burrows-wheeler-transform.jsx",
            ),
            (
                "git:git://github.com/alaz/mongo-scala-driver.git",
                "alaz/mongo-scala-driver",
            ),
            (
                "git:git@github.com:doug-martin/string-extended.git",
                "doug-martin/string-extended",
            ),
            (
                "git:github.com//dominictarr/level-couch-sync.git",
                "dominictarr/level-couch-sync",
            ),
            ("git:github.com/dominictarr/keep.git", "dominictarr/keep"),
            ("git:https://github.com/vaadin/cdi.git", "vaadin/cdi"),
            ("git@git@github.com:dead-horse/webT.git", "dead-horse/webT"),
            ("git@github.com:agilemd/then.git", "agilemd/then"),
            ("https : //github.com/alex101/texter.js.git", "alex101/texter.js"),
            ("git@git.github.com:daddye/stitchme.git", "daddye/stitchme"),
            (
                "github.com/1995hnagamin/hubot-achievements",
                "1995hnagamin/hubot-achievements",
            ),
            (
                "git//github.com/divyavanmahajan/jsforce_downloader.git",
                "divyavanmahajan/jsforce_downloader",
            ),
            (
                "scm:git:https://michaelkrog@github.com/michaelkrog/filter4j.git",
                "michaelkrog/filter4j",
            ),
            ("github.com/github/combobox-nav", "github/combobox-nav"),
            ("github.com/hhao785/github.com", "hhao785/github.com"),
            ("github.com/contrived_example/githubcom", "contrived_example/githubcom"),
            (
                "scm:git:ssh://github.com/an-organization/a-repository.git/a-repository-subdirectory",
                "an-organization/a-repository",
            ),
        ],
    )
    def test_parse(self, url: str, full_name: str):
        assert GithubURLParser.parse(url) == full_name

    def test_handle_anchors(self):
        full_name = "michaelkrog/filter4j"
        url = "scm:git:https://michaelkrog@github.com/michaelkrog/filter4j.git#anchor"
        assert GithubURLParser.parse(url) == full_name

    def test_handle_querystrings(self):
        full_name = "michaelkrog/filter4j"
        url = "scm:git:https://michaelkrog@github.com/michaelkrog/filter4j.git?foo=bar&wut=wah"
        assert GithubURLParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "[scm:git:https://michaelkrog@github.com/michaelkrog/filter4j.git]",
                "michaelkrog/filter4j",
            ),
            (
                "<scm:git:https://michaelkrog@github.com/michaelkrog/filter4j.git>",
                "michaelkrog/filter4j",
            ),
            (
                "(scm:git:https://michaelkrog@github.com/michaelkrog/filter4j.git)",
                "michaelkrog/filter4j",
            ),
        ],
    )
    def test_handle_brackets(self, url: str, full_name: str):
        assert GithubURLParser.parse(url) == full_name

    @pytest.mark.parametrize(
        "url",
        [
            "https://google.com",
            "https://github.com/foo",
            "https://github.com",
            "https://foo.github.io",
            "https://github.ibm.com/apiconnect/apiconnect",
        ],
    )
    def test_parse_non_github_urls(self, url: str):
        assert GithubURLParser.parse(url) == None

    def test_case_sensitive(self):
        assert GithubURLParser.CASE_SENSITIVE == False


class TestGitlabURLParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            ("https://gitlab.com/maxcdn/shml/", "maxcdn/shml"),
            (
                "git+https://gitlab.com/hugojosefson/express-cluster-stability.git",
                "hugojosefson/express-cluster-stability",
            ),
            ("www.gitlab.com/37point2/brainfuckifyjs", "37point2/brainfuckifyjs"),
            ("ssh+git@gitlab.com:omardelarosa/tonka-npm.git", "omardelarosa/tonka-npm"),
            (
                "scm:svn:https://gitlab.com/tanhaichao/top4j/tags/top4j-0.0.1",
                "tanhaichao/top4j",
            ),
            (
                "scm:${project.scm.vendor}:git@gitlab.com:adamcin/maven-s3-wagon.git",
                "adamcin/maven-s3-wagon",
            ),
            ("scm:https://vert-x@gitlab.com/purplefox/vert.x", "purplefox/vert.x"),
            ("scm:https:https://gitlab.com/vaadin/vaadin.git", "vaadin/vaadin"),
            (
                "scm:https://gitlab.com/daimajia/AndroidAnimations.git",
                "daimajia/AndroidAnimations",
            ),
            ("scm:http:http://NICTA@gitlab.com/NICTA/scoobi.git", "NICTA/scoobi"),
            (
                "scm:http:http://etorreborre@gitlab.com/etorreborre/specs.git",
                "etorreborre/specs",
            ),
            (
                "scm:hg:https://gitlab.com/wangenyong/EnAndroidLibrary",
                "wangenyong/EnAndroidLibrary",
            ),
            ("scm:hg:git://gitlab.com/jesselong/muffero.git", "jesselong/muffero"),
            (
                "scm:git:ssh@gitlab.com:claudius108/maven-plugins.git",
                "claudius108/maven-plugins",
            ),
            (
                "scm:git|ssh://git@gitlab.com/zinin/tomcat-redis-session.git",
                "zinin/tomcat-redis-session",
            ),
            (
                "scm:git:prasadpnair@gitlab.com/Jamcracker/jit-core.git",
                "Jamcracker/jit-core",
            ),
            (
                "scm:git:scm:git:git://gitlab.com/spring-projects/spring-integration.git",
                "spring-projects/spring-integration",
            ),
            ("scm:git:https://gitlab.com/axet/sqlite4java", "axet/sqlite4java"),
            ("scm:git:https://gitlab.com/celum/db-tool.git", "celum/db-tool"),
            (
                "scm:git:https://ffromm@gitlab.com/jenkinsci/slave-setup-plugin.git",
                "jenkinsci/slave-setup-plugin",
            ),
            ("scm:git:gitlab.com/yfcai/CREG.git", "yfcai/CREG"),
            (
                "scm:git@gitlab.com:urunimi/PullToRefreshAndroid.git",
                "urunimi/PullToRefreshAndroid",
            ),
            ("scm:git:gitlab.com/larsrh/libisabelle.git", "larsrh/libisabelle"),
            ("scm:git://gitlab.com/lihaoyi/ajax.git", "lihaoyi/ajax"),
            ("scm:git@gitlab.com:ExpediaInc/ean-android.git", "ExpediaInc/ean-android"),
            ("https://RobinQu@gitlab.com/RobinQu/node-gear.git", "RobinQu/node-gear"),
            (
                "https://taylorhakes@gitlab.com/taylorhakes/promise-polyfill.git",
                "taylorhakes/promise-polyfill",
            ),
            ("https://gf3@gitlab.com/gf3/IRC-js.git", "gf3/IRC-js"),
            ("https://crcn:KQ3Lc6za@gitlab.com/crcn/verify.js.git", "crcn/verify.js"),
            ("//gitlab.com/dtrejo/report.git", "dtrejo/report"),
            (
                "=https://gitlab.com/amansatija/Cus360MavenCentralDemoLib.git",
                "amansatija/Cus360MavenCentralDemoLib",
            ),
            ("git+https://bebraw@gitlab.com/bebraw/colorjoe.git", "bebraw/colorjoe"),
            (
                "git:///gitlab.com/NovaGL/homebridge-openremote.git",
                "NovaGL/homebridge-openremote",
            ),
            (
                "git://git@gitlab.com/jballant/webpack-strip-block.git",
                "jballant/webpack-strip-block",
            ),
            (
                "git://gitlab.com/2betop/yogurt-preprocessor-extlang.git",
                "2betop/yogurt-preprocessor-extlang",
            ),
            ("git:/git://gitlab.com/antz29/node-twister.git", "antz29/node-twister"),
            (
                "git:/gitlab.com/shibukawa/burrows-wheeler-transform.jsx.git",
                "shibukawa/burrows-wheeler-transform.jsx",
            ),
            (
                "git:git://gitlab.com/alaz/mongo-scala-driver.git",
                "alaz/mongo-scala-driver",
            ),
            (
                "git:git@gitlab.com:doug-martin/string-extended.git",
                "doug-martin/string-extended",
            ),
            (
                "git:gitlab.com//dominictarr/level-couch-sync.git",
                "dominictarr/level-couch-sync",
            ),
            ("git:gitlab.com/dominictarr/keep.git", "dominictarr/keep"),
            ("git:https://gitlab.com/vaadin/cdi.git", "vaadin/cdi"),
            ("git@git@gitlab.com:dead-horse/webT.git", "dead-horse/webT"),
            ("git@gitlab.com:agilemd/then.git", "agilemd/then"),
            ("https : //gitlab.com/alex101/texter.js.git", "alex101/texter.js"),
            ("git@git.gitlab.com:daddye/stitchme.git", "daddye/stitchme"),
            (
                "gitlab.com/1995hnagamin/hubot-achievements",
                "1995hnagamin/hubot-achievements",
            ),
            (
                "git//gitlab.com/divyavanmahajan/jsforce_downloader.git",
                "divyavanmahajan/jsforce_downloader",
            ),
            (
                "scm:git:https://michaelkrog@gitlab.com/michaelkrog/filter4j.git",
                "michaelkrog/filter4j",
            ),
        ],
    )
    def test_parse(self, url: str, full_name: str):
        assert GitlabURLParser.parse(url) == full_name

    def test_handle_anchors(self):
        full_name = "michaelkrog/filter4j"
        url = "scm:git:https://michaelkrog@gitlab.com/michaelkrog/filter4j.git#anchor"
        assert GitlabURLParser.parse(url) == full_name

    def test_handle_querystrings(self):
        full_name = "michaelkrog/filter4j"
        url = "scm:git:https://michaelkrog@gitlab.com/michaelkrog/filter4j.git?foo=bar&wut=wah"
        assert GitlabURLParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "[scm:git:https://michaelkrog@gitlab.com/michaelkrog/filter4j.git]",
                "michaelkrog/filter4j",
            ),
            (
                "<scm:git:https://michaelkrog@gitlab.com/michaelkrog/filter4j.git>",
                "michaelkrog/filter4j",
            ),
            (
                "(scm:git:https://michaelkrog@gitlab.com/michaelkrog/filter4j.git)",
                "michaelkrog/filter4j",
            ),
        ],
    )
    def test_handle_brackets(self, url: str, full_name: str):
        assert GitlabURLParser.parse(url) == full_name

    @pytest.mark.parametrize(
        "url",
        [
            "https://google.com",
            "https://gitlab.com/foo",
            "https://gitlab.com",
            "https://foo.gitlab.io",
            "https://gitlab.ibm.com/apiconnect/apiconnect",
        ],
    )
    def test_parse_non_gitlab_urls(self, url: str):
        assert GitlabURLParser.parse(url) == None

    def test_case_sensitive(self):
        assert GitlabURLParser.CASE_SENSITIVE == False


class TestSourceforgeUrlParser:
    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            ("https://sourceforge.net/projects/libpng", "libpng"),
            ("https://sourceforge.net/p/libpng/code/ci/master/tree/ci", "libpng"),
        ],
    )
    def test_parse(self, url: str, full_name: str):
        assert SourceforgeUrlParser.parse(url) == full_name

    @pytest.mark.parametrize(
        ("url", "full_name"),
        [
            (
                "https://sourceforge.net/projects/libpng",
                "https://sourceforge.net/projects/libpng",
            ),
            (
                "https://sourceforge.net/p/libpng/code/ci/master/tree/ci",
                "https://sourceforge.net/projects/libpng",
            ),
        ],
    )
    def test_parse_to_full_url(self, url: str, full_name: str):
        assert SourceforgeUrlParser.parse_to_full_url(url) == full_name

    def test_sourceforge_jp_urls(self):
        assert (
            SourceforgeUrlParser.parse("http://svn.sourceforge.jp/svnroot/foo/") == None
        )

    def test_case_sensitive(self):
        assert SourceforgeUrlParser.CASE_SENSITIVE == False
