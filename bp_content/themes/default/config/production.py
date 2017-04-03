config = {

    # This config file will be detected in production environment and values defined here will overwrite those in config.py
    'environment': "production",
    'app_name': "Social Analyzer",
    # contact page email settings
    'contact_sender': "alexsmx@gmail.com",
    'contact_recipient': "alexsmx@gmail.com",

    'send_mail_developer': False,
    # ----> ADD MORE CONFIGURATION OPTIONS HERE <----
    # ----> ADD MORE CONFIGURATION OPTIONS HERE <----
    'aes_key': "9c20576a4330bbe719b23ac8bf3bb8a1",
    'salt': "RdbkETeF$<^>%%X^8|e[9td62`dobFL[V&F&**@`UP6vqjGL,>v+k@ma^zd6WdG0;H>o-SGG9ynk",
    'captcha_public_key': "6Ldi0u4SAAAAAC8pjDop1aDdmeiVrUOU2M4i23tT",
    'captcha_private_key': "6Ldi0u4SAAAAAPzk1gaFDRQgry7XW4VBvNCqCHuJ",
     # callback url must be: http://[YOUR DOMAIN]/login/facebook/complete
    'fb_api_key': '1305386492874661',
    'fb_secret': '9dede123331989c60427ff0dec0f0878',
    'enable_federated_login': False,
    'google_analytics_code': """
            <script>
            (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
            (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
            m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
            })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

            ga('create', 'UA-47489500-1', 'auto', {'allowLinker': true});
            ga('require', 'linker');
            ga('linker:autoLink', ['beecoss.com', 'blog.beecoss.com', 'appengine.beecoss.com']);
            ga('send', 'pageview');
            </script>
        """,
}
