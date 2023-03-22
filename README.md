## Superinference

Superinference is a library that infers analysis-ready attributes from a person's social media username or unique identifier and returns them as JSON objects.

It supports both token-based (OAuth) authorization for authenticated requests and unauthenticated requests for public data. It currently supports the following social media channels:

- [x] GitHub
- [x] Dev.to
- [ ] LinkedIn
- [ ] Medium
- [ ] WordPress


It is currently actively being developed so more supported social media channels will be added in the future.

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

There is nothing magic here. Superinference is just a wrapper around the social media APIs and so it's usage is very simple. Here is how you would extract and infer attributes from a person using his/her GitHub username:

```py
from superinference.github import GithubProfile
githubprofile = GithubProfile(username="aurelliachristie")
githubprofile.perform_inference()
```

Output:

```
PLACEHOLDER
```

And here is another example using a Dev.to username:

```py
from superinference.github import DevtoProfile
devtoprofile = DevtoProfile(username="onlyphantom")
devtoprofile.perform_inference()
```

Output:

```
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
'https://res.cloudinary.com/practicaldev/image/fetch/s--NtWnKwMa--/c_fill,f_auto,fl_progressive,h_320,q_auto,w_320/
https://dev-to-uploads.s3.amazonaws.com/uploads/user/profile_image/189820/60729a40-2c6e-4d65-8cc9-18421fc9626e.jpg'
}
```

### Authenticated Requests

The calls in the code example above are unauthorized requests, so it collects data from public profiles and returns information that is available to the public. 

You can optionally pass in an OAuth token to make authenticated requests to, in the case of GitHub, which provide the capability to extract and infer stats from private repositories not available to the public.

```py
githubprofile = GithubProfile(username="onlyphantom",access_token=access_token)
devtoprofile.perform_inference(top_repo_n=10, top_language_n=5, closest_user_n=5, include_private=True)
```

This returns the top 10 repositories, including private ones, the top 5 languages, and the closest 5 users using a GitHub OAuth token.

### API Rate Limit

The APIs we use restrict the number of requests that can be made within a set timeframe. If this limit is exceeded, the API looping will cease and we will provide the inference from the data we have collected thus far. To see this information, you can check the `..._api_message` parameter included in the response. We include this parameter in all responses that are affected. An example of this message can be seen in the code snippet below:

```
{
  ...,
  "commit_api_message": "Hey there! Looks like the inference above is from the latest 800 commits since you've reached the API rate limit 😉"
}
```
