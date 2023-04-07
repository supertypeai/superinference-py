## Superinference

Superinference is a library that infers analysis-ready attributes from a person's social media username or unique identifier and returns them as JSON objects. The development of Superinference was initiated by [Aurellia Christie](https://github.com/AurelliaChristie) and other members of [Supertype](https://github.com/supertypeai), who created a Javascript library that can be accessed [here](https://github.com/supertypeai/superinference).

It supports both token-based (OAuth) authorization for authenticated requests and unauthenticated requests for public data. It currently supports the following social media channels:

- [x] GitHub
- [x] Dev.to
- [ ] LinkedIn
- [ ] Medium
- [ ] WordPress


### Live Demo:
Check out [this Colab notebook](https://colab.research.google.com/drive/1k8N1OvVGo8HJCYOOFPS6FhnPBsZ_aMXK?usp=sharing) to quickly experiment with Superinference.

### Use Cases

You might use superinference to generate profile pages of your app users, or to enrich your user data with additional information by inferring them from their social media accounts. You might also use it to accelerate your account creation process by directly inferring attributes such as their email address, name, and profile picture.

## Installation

You can install the package using `pip`:
    
```bash
pip install superinference
```
## Requirements

```py
requests==2.28.1
rich==13.3.2
```

## Usage

### Common Patterns

There is nothing magic here. Superinference is just a wrapper around the social media APIs and so it's usage is very simple. Here is how you would extract and infer attributes (`profile`, `skill`, `stats`, `contribution`) from a person using his/her GitHub username:

```py
from superinference.github import GithubProfile
githubprofile = GithubProfile(username="AurelliaChristie")
githubprofile.perform_inference()
```

Output:

```bash
{
    'profile': {
        'login': 'AurelliaChristie',
        'name': 'Aurellia Christie',
        'company': '@supertypeai ',
        'blog': '',
        'location': None,
        'email': None,
        'hireable': None,
        'twitter_username': None,
        'avatar_url': 'https://avatars.githubusercontent.com/u/69672839?v=4',
        'bio': 'Full Stack Data Scientist at @supertypeai',
        'followers': 8,
        'following': 8
    },
    'skill': {
        # based on the user's owned repositories data, profile bio and profile README
        'inference_from_originalrepo_count': 17,
        'key_qualifications': ['data-scientist', 'data', 'consultancy', 'full-stack-developer'],
        'top_n_languages': ['html', 'javascript', 'python'],
        'languages_percentage': {
            # only available for authorized request, otherwise will return null
            'html': 0.529,
            'javascript': 0.353,
            'python': 0.294,
            'css': 0.235,
            'r': 0.059,
            'jupyter-notebook': 0.059
        }
    },
    'stats': {
        'incomplete_repo_results': False,
        'inference_from_repo_count': 26,
        'original_repo_count': 17,
        'forked_repo_count': 9,
        'counts': {'stargazers_count': 2, 'forks_count': 4},
        'top_repo_stars_forks': [
            {
                'name': 'Ad-Fatigued-List-Generator',
                'html_url': 'https://github.com/AurelliaChristie/Ad-Fatigued-List-Generator',
                'description': None,
                'top_language': 'Python',
                'stargazers_count': 0,
                'forks_count': 1
            },
            {
                'name': 'BeautIndonesia',
                'html_url': 'https://github.com/AurelliaChristie/BeautIndonesia',
                ...
            },
            {
                'name': 'cryptocurrency',
                'html_url': 'https://github.com/AurelliaChristie/cryptocurrency',
                ...
            }
        ]
    },
    'contribution': {
        # only available for authorized request, otherwise will return null
        'contribution_count': 1081,
        'weekly_average_contribution': 7.833,
        'contribution_count_per_day': {
            # the first value represents the contributions count in the last 12 months, 
            # while the second value represents the contributions count of all time
            'Wed': [106, 219],
            'Thu': [80, 198],
            'Fri': [66, 226],
            'Mon': [54, 161],
            'Tue': [44, 176],
            'Sun': [11, 52],
            'Sat': [6, 49]
        },
        'contribution_count_per_month': {
            # the first value represents the contributions count in the last 12 months, 
            # while the second value represents the contributions count of all time
            'Mar': [120, 169],
            'Feb': [88, 162],
            'Aug': [32, 42],
            'Oct': [24, 163],
            'Jul': [22, 56],
            'Sep': [19, 73],
            'Jun': [18, 25],
            'Apr': [16, 26],
            'Nov': [15, 75],
            'Jan': [6, 190],
            'May': [4, 27],
            'Dec': [3, 73]
        },
        # the following 4 properties are inferred from the top 100 repos per year based on the total contributions count
        'contribution_count_per_owned_repo': {
            'BeautIndonesia': 84,
            'TWO': 52,
            'Skilvul-Tech4impact': 34,
            'Ad-Fatigued-List-Generator': 32,
            'Inventory-Management': 15,
            '21_JSIntermediate_Code_Challenge': 15,
            'Skilvul-Git-Second-Assignment': 14,
            'Learning-Django': 9,
            'Statistics-and-Microsoft-Excel-101': 7,
            'Using-R-for-Time-Series-Stock-Analysis': 5,
            'Multivariate-Analysis-McD-and-KFC-Nutrition-Facts': 5,
            'cryptocurrency': 4,
            'AurelliaChristie': 3,
            'express-heroku-todolist': 2,
            'dashboard-training': 2,
            'Documentations': 2,
            'supertype-fellowship': 1
        },
        'contribution_count_per_other_repo': [
            {
                'name': 'Toyota',
                'owner': 'supertypeai',
                'html_url': 'https://github.com/supertypeai/Toyota',
                'description': None,
                'top_language': None,
                'contributions_count': 181
            },
            {
                'name': 'generations-frontend',
                'owner': 'onlyphantom',
                'html_url': 'https://github.com/onlyphantom/generations-frontend',
                'description': 'Front end for Fellowship by @supertypeai',
                'top_language': 'javascript',
                'contributions_count': 176
            },
            {
                'name': 'CookInd',
                'owner': 'Tech4Impact-21-22',
                ...
            },
            ...
        ],
        'contribution_count_per_repo_org_owner': {
            'supertypeai': 396,
            'Tech4Impact-21-22': 124,
            'olahdata-ai': 2,
            'impactbyte': 1,
            'supabase': 1
        },
        'contribution_count_per_repo_user_owner': {
            'AurelliaChristie': 286,
            'onlyphantom': 215,
            'Lathh': 18,
            'vccalvin33': 9
        },
        # incoming contribution count (commits and pull requests from other users)
        # only based on the top and latest 10 repositories
        'external_contribution_to_top_10_repo': {'geraldbryan': 42}
    }
}
```

And here is another example using a Dev.to username:

```py
from superinference.github import DevtoProfile
devtoprofile = DevtoProfile(username="onlyphantom")
devtoprofile.perform_inference()
```

Output:

```bash
{
    'type_of': 'user',
    'id': 189820,
    'username': 'onlyphantom',
    'name': 'Samuel Chan',
    'twitter_username': '_onlyphantom',
    'github_username': 'onlyphantom',
    'summary': 'Three-time entrepreneur. Co-founder of Algoritma, a data science academy; https://supertype.ai, a 
full-cycle data science agency; GrowthBot (chatbot on Slack). Building: Learnblockchain.academy',
    'location': 'Indonesia / Singapore',
    'website_url': 'https://www.youtube.com/samuelchan',
    'joined_at': 'Jul  3, 2019',
    'profile_image': 
'https://res.cloudinary.com/practicaldev/image/fetch/...
}
```

### Authenticated Requests

The calls in the code example above are unauthorized requests, so it collects data from public profiles and returns information that is available to the public. 

You can optionally pass in an OAuth token to make authenticated requests to, in the case of GitHub, which provide the capability to extract and infer stats from private repositories not available to the public.

```py
githubprofile = GithubProfile(username="onlyphantom",access_token=access_token)
devtoprofile.perform_inference(top_repo_n=10, top_language_n=5, include_private=True)
```

This returns the top 10 repositories, including private ones, and the top 5 languages using a GitHub OAuth token.

### API Rate Limit

The APIs we use restrict the number of requests that can be made within a set timeframe. If this limit is exceeded, the API looping will cease and we will provide the inference from the data we have collected thus far. To see this information, you can check the following parameters included in the response:
- `incomplete_<item>_results`: Boolean that indicates if the results for `<item>` are incomplete due to reaching the API rate limit.
- `inference_from_<item>_count`: The number of `<item>` got from the API (before reaching the API rate limit).

**Special notes for GitHub API : the API can only return maximum 1,000 results (10 pages) per endpoint. Thus there will be a case where you see the `incomplete_<item>_results` set to `false` while the `inference_from_<item>_count` set to `1,000` even though there supposed to be more than 1,000 `<items>`.**
