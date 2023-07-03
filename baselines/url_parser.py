import re
from typing import Optional


class URLParser:
    """reimplementation of the [`URLParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/url_parser.rb) class of `librariesio-url-parser` package."""

    CASE_SENSITIVE = False

    def __init__(self, url: str) -> None:
        self.url = url

    @classmethod
    def try_all(cls, url: str) -> Optional[str]:
        """reimplementation of class method [`try_all`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/url_parser.rb#L33)"""

        # a tricky implementation of class method [`all_parsers`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/url_parser.rb#L66)
        # all_parsers contain all subclasses of URLParser
        all_parsers = [
            AndroidGooglesourceUrlParser,
            ApacheGitWipUrlParser,
            ApacheGitboxUrlParser,
            ApacheSvnUrlParser,
            BitbucketURLParser,
            DrupalUrlParser,
            EclipseGitUrlParser,
            GithubURLParser,
            GitlabURLParser,
            SourceforgeUrlParser,
        ]

        for parser in all_parsers:
            result = parser.parse_to_full_url(url)
            if result:
                return result

    @classmethod
    def parse_to_full_url(cls, url: str) -> Optional[str]:
        """reimplementation of class method [`parse_to_full_url`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/url_parser.rb#L25)"""
        return cls(url).parse_to_full_url_instance()

    def parse_to_full_url_instance(self) -> Optional[str]:
        """reimplementation of instance method [`parse_to_full_url`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/url_parser.rb#L42)"""
        path = self.parse_instance()
        if not path or len(path) == 0:
            return None

        return "/".join([self.full_domain, path])

    @property
    def full_domain(self) -> str:
        raise NotImplementedError

    @classmethod
    def parse(cls, url: str) -> Optional[str]:
        return cls(url).parse_instance()

    def parse_instance(self) -> Optional[str]:
        """reimplementation of instance method [`parse`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/url_parser.rb#L14)"""
        if not self.parseable():
            return None
        extracted_url = self.extractable_early()

        if extracted_url:
            return extracted_url

        self.clean_url()
        return self.format_url()

    def parseable(self) -> bool:
        """reimplementation of instance method [`parseable`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/url_parser.rb#L111)"""
        return self.url and self.domain in self.url

    @property
    def domain(self) -> str:
        raise NotImplementedError

    @property
    def tlds(self) -> list[str]:
        raise NotImplementedError

    @property
    def domain_regex(self) -> str:
        return f"{self.domain}\.({'|'.join(self.tlds)})"

    def website_url(self) -> str:
        return re.search(
            r"www\.{}".format(self.domain_regex), self.url, flags=re.IGNORECASE
        )

    def extractable_early(self) -> Optional[str]:
        """reimplementation of instance method [`extractable_early`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/url_parser.rb#L135)"""
        if self.website_url():
            return None

        match = re.search(
            r"([\w\.@\:\-_~]+)\.{}\/([\w\.@\:\-\_\~]+)".format(self.domain_regex),
            self.url,
            flags=re.IGNORECASE,
        )

        if match and len(match.groups()) == 3:
            return f"{match.group(1)}/{match.group(3)}"

    def clean_url(self) -> None:
        """reimplementation of instance method [`clean_url`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/url_parser.rb#L42)"""
        self.remove_whitespace()
        self.remove_brackets()
        self.remove_anchors()
        self.remove_querystring()
        self.remove_auth_user()
        self.remove_equals_sign()
        self.remove_scheme()

        if not self.includes_domain():
            self.url = None
            return None
        self.remove_subdomain()
        self.remove_domain()
        self.remove_git_scheme()
        self.remove_extra_segments()
        self.remove_git_extension()

    def remove_whitespace(self) -> None:
        self.url = re.sub(r"\s", "", self.url)

    def remove_brackets(self) -> None:
        self.url = re.sub(r">|<|\(|\)|\[|\]", "", self.url)

    def remove_anchors(self) -> None:
        self.url = re.sub(r"(#\S*)$", "", self.url, flags=re.IGNORECASE)

    def remove_querystring(self) -> None:
        self.url = re.sub(r"(\?\S*)$", "", self.url, flags=re.IGNORECASE)

    def remove_auth_user(self) -> None:
        self.url = self.url.split("@")[-1]

    def remove_equals_sign(self) -> None:
        self.url = self.url.split("=")[-1]

    def remove_scheme(self) -> None:
        self.url = re.sub(
            r"(((git\+https|git|ssh|hg|svn|scm|http|https)+?:)(\/\/)?)",
            "",
            self.url,
            flags=re.IGNORECASE,
        )

    def includes_domain(self) -> bool:
        if not re.search(
            r"{}".format(self.domain_regex), self.url, flags=re.IGNORECASE
        ):
            return False
        return True

    def remove_subdomain(self) -> None:
        self.url = re.sub(
            r"(www|ssh|raw|git|wiki|svn)+?\.", "", self.url, flags=re.IGNORECASE
        )

    def remove_git_scheme(self) -> None:
        self.url = re.sub(r"git\/\/", "", self.url, flags=re.IGNORECASE)

    def remove_extra_segments(self) -> None:
        self.url = [s for s in self.url.split("/") if s.strip()][:2]

    def remove_git_extension(self) -> None:
        if isinstance(self.url, list):
            if self.url:
                self.url[-1] = re.sub(
                    r"(\.git|\/)$", "", self.url[-1], flags=re.IGNORECASE
                )
        else:
            self.url = re.sub(r"(\.git|\/)$", "", self.url, flags=re.IGNORECASE)

    def remove_domain(self) -> None:
        raise NotImplementedError

    def format_url(self) -> Optional[str]:
        if not self.url or len(self.url) != 2:
            return None
        return "/".join(self.url)


class AndroidGooglesourceUrlParser(URLParser):
    """reimplementation of the [`AndroidGooglesourceUrlParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/android_googlesource_url_parser.rb) class of `librariesio-url-parser` package."""

    CASE_SENSITIVE = True

    @property
    def full_domain(self) -> str:
        return "https://android.googlesource.com"

    @property
    def tlds(self) -> list[str]:
        return ["com"]

    @property
    def domain(self) -> str:
        return "android.googlesource"

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(android\.googlesource\.com)+?(:|\/)?",
            "",
            self.url,
            1,
            flags=re.IGNORECASE,
        )

    def remove_extra_segments(self) -> None:
        self.url = [s for s in self.url.split("/") if s.strip()]

    def format_url(self):
        if not isinstance(self.url, list) or len(self.url) <= 0:
            return None

        return "/".join(self.url).split("+")[0].rstrip("/")


class ApacheGitWipUrlParser(URLParser):
    """reimplementation of the [`ApacheGitWipUrlParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/apache_git_wip_url_parser.rb) class of `librariesio-url-parser` package."""

    CASE_SENSITIVE = True

    @property
    def full_domain(self) -> str:
        return "https://git-wip-us.apache.org/repos/asf"

    @property
    def tlds(self) -> list[str]:
        return ["org"]

    @property
    def domain(self) -> str:
        return "git-wip-us.apache"

    def remove_querystring(self) -> None:
        return self.url

    def remove_equals_sign(self) -> None:
        splits = self.url.split("=")
        p_index = next(
            (i for i, s in enumerate(splits) if s.endswith("?p") or s.endswith("&p")),
            None,
        )

        if p_index is not None:
            new_url = "=".join(splits[: p_index + 2])
            new_url = re.sub(r"[;,&].*", "", new_url)
            self.url = new_url

    @property
    def domain_regex(self) -> str:
        return f"{self.domain.split('/')[0]}\.({'|'.join(self.tlds)})\/repos/asf"

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(git-wip-us\.apache\.org\/(repos\/asf))+?(:|\/)?",
            "",
            self.url,
            1,
            flags=re.IGNORECASE,
        )

    def remove_extra_segments(self) -> None:
        if isinstance(self.url, str) and self.url.startswith("?p="):
            self.url = self.url.split("=")[-1]

    def format_url(self) -> Optional[str]:
        if isinstance(self.url, str):
            return self.url
        return None


class ApacheGitboxUrlParser(URLParser):
    """reimplementation of the [`ApacheGitboxUrlParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/apache_gitbox_url_parser.rb) class of `librariesio-url-parser` package."""

    CASE_SENSITIVE = True

    @property
    def full_domain(self) -> str:
        return "https://gitbox.apache.org/repos/asf"

    @property
    def tlds(self) -> list[str]:
        return ["org"]

    @property
    def domain(self) -> str:
        return "gitbox.apache"

    def remove_querystring(self) -> None:
        return self.url

    def remove_equals_sign(self) -> None:
        splits = self.url.split("=")
        p_index = next(
            (i for i, s in enumerate(splits) if s.endswith("?p") or s.endswith("&p")),
            None,
        )

        if p_index is not None:
            new_url = "=".join(splits[: p_index + 2])
            new_url = re.sub(r"[;,&].*", "", new_url)
            self.url = new_url

    @property
    def domain_regex(self) -> str:
        return f"{self.domain.split('/')[0]}\.({'|'.join(self.tlds)})\/repos/asf"

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(gitbox\.apache\.org\/(repos\/asf))+?(:|\/)?",
            "",
            self.url,
            1,
            flags=re.IGNORECASE,
        )

    def remove_extra_segments(self) -> None:
        if isinstance(self.url, str) and self.url.startswith("?p="):
            self.url = self.url.split("=")[-1]

    def format_url(self) -> Optional[str]:
        if isinstance(self.url, str):
            return self.url
        return None


class ApacheSvnUrlParser(URLParser):
    """reimplementation of the [`ApacheSvnUrlParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/apache_svn_url_parser.rb) class of `librariesio-url-parser` package."""

    SUBDIR_NAMES = ("trunk", "tags", "branches")
    VALID_PATHS = ("viewvc", r"viewcvs\.cgi", r"repos\/asf")
    CASE_SENSITIVE = True

    @property
    def full_domain(self) -> str:
        return "https://svn.apache.org/viewvc"

    @property
    def tlds(self) -> list[str]:
        return ["org"]

    @property
    def domain(self) -> str:
        return "svn.apache"

    @property
    def domain_regex(self) -> str:
        return f"{self.domain}\.({'|'.join(self.tlds)})\/({'|'.join(self.VALID_PATHS)})"

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(apache\.org\/(viewvc|repos\/asf|viewcvs\.cgi))+?(:|\/)?",
            "",
            self.url,
            1,
            flags=re.IGNORECASE,
        )

    def extractable_early(self) -> Optional[str]:
        return None

    def remove_extra_segments(self) -> None:
        self.url = [s for s in self.url.split("/") if s.strip()]
        subdir_index = next(
            (i for i, s in enumerate(self.url) if s in self.SUBDIR_NAMES), None
        )
        if subdir_index:
            in_maven_pom_dir = "/".join(self.url[:2]).lower() == "maven/pom"
            if in_maven_pom_dir:
                self.url = self.url[: subdir_index + 2]
            else:
                self.url = self.url[:subdir_index]

    def format_url(self) -> Optional[str]:
        if isinstance(self.url, list) and len(self.url) > 0:
            return "/".join(self.url)
        return None


class BitbucketURLParser(URLParser):
    """reimplementation of the [`BitbucketURLParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/bitbucket_url_parser.rb) class of `librariesio-url-parser` package."""

    @property
    def full_domain(self) -> str:
        return "https://bitbucket.org"

    @property
    def tlds(self) -> list[str]:
        return ["com", "org"]

    @property
    def domain(self) -> str:
        return "bitbucket"

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(bitbucket\.com|bitbucket\.org)+?(:|\/)?",
            "",
            self.url,
            1,
            flags=re.IGNORECASE,
        )


class DrupalUrlParser(URLParser):
    """reimplementation of the [`DrupalUrlParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/drupal_url_parser.rb) class of `librariesio-url-parser` package."""

    @property
    def full_domain(self) -> str:
        return "https://git.drupalcode.org/project"

    @property
    def tlds(self) -> list[str]:
        return ["org"]

    @property
    def domain(self) -> str:
        return "git.drupalcode"

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(drupalcode\.org\/project)+?(:|\/)?", "", self.url, 1, flags=re.IGNORECASE
        )

    def format_url(self) -> str | None:
        if isinstance(self.url, list) and len(self.url) > 0:
            return "/".join(self.url)
        return None


class EclipseGitUrlParser(URLParser):
    """reimplementation of the [`EclipseGitUrlParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/eclipse_git_url_parser.rb) class of `librariesio-url-parser` package."""

    CASE_SENSITIVE = True

    @property
    def full_domain(self) -> str:
        return "https://git.eclipse.org/c"

    @property
    def tlds(self) -> list[str]:
        return ["org"]

    @property
    def domain(self) -> str:
        return "git.eclipse"

    def remove_git_extension(self) -> None:
        return None

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(eclipse\.org\/c)+?(:|\/)?", "", self.url, 1, flags=re.IGNORECASE
        )


class GithubURLParser(URLParser):
    """reimplementation of the [`GithubURLParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/github_url_parser.rb) class of `librariesio-url-parser` package."""

    @property
    def full_domain(self) -> str:
        return "https://github.com"

    @property
    def tlds(self) -> list[str]:
        return ["io", "com", "org"]

    @property
    def domain(self) -> str:
        return "github"

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(github\.io|github\.com|github\.org|raw\.githubusercontent\.com)+?(:|\/)?",
            "",
            self.url,
            1,
            flags=re.IGNORECASE,
        )


class GitlabURLParser(URLParser):
    """reimplementation of the [`GitlabURLParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/gitlab_url_parser.rb) class of `librariesio-url-parser` package."""

    @property
    def full_domain(self) -> str:
        return "https://gitlab.com"

    @property
    def tlds(self) -> list[str]:
        return ["com"]

    @property
    def domain(self) -> str:
        return "gitlab"

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(gitlab\.com)+?(:|\/)?", "", self.url, 1, flags=re.IGNORECASE
        )


class SourceforgeUrlParser(URLParser):
    """reimplementation of the [`SourceforgeUrlParser`](https://github.com/librariesio/librariesio-url-parser/blob/main/lib/sourceforge_url_parser.rb) class of `librariesio-url-parser` package."""

    PROJECT_PATHS = ("projects", "p")

    @property
    def full_domain(self) -> str:
        return "https://sourceforge.net/projects"

    @property
    def tlds(self) -> list[str]:
        return ["net"]

    @property
    def domain(self) -> str:
        return "sourceforge"

    def remove_domain(self) -> None:
        self.url = re.sub(
            r"(sourceforge\.net\/({}))+?(:|\/)?".format("|".join(self.PROJECT_PATHS)),
            "",
            self.url,
            1,
            flags=re.IGNORECASE,
        )

    def extractable_early(self) -> str | None:
        return None

    def remove_extra_segments(self) -> None:
        url_parts = [s for s in self.url.split("/") if s.strip()]
        if url_parts:
            self.url = url_parts[0]

    def format_url(self) -> str | None:
        if isinstance(self.url, str):
            return self.url
        return None
