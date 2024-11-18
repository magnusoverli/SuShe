# SuShe (SuperSheet)

SuShe is a very basic desktop aplication, aimed at creating rich and coherent "album-of-the-year" lists for personal use.
It is written in pytyon and using PyQt6 for the GUI framework.

![{D2AB3F09-C63F-4AB4-A83D-5D551C860F68}](https://github.com/user-attachments/assets/a4616d42-bdd4-4d13-b4ef-7b0496296d25)


## Background

SuShe (SuperSheet) was born out of the need to standardize album-of-year award lists. Myself and a group of like minded people where arranging the annual Metal Awards, and saw the need to have the members' lists in a more standadrized form.
This lead to several tests with Excel and Google Sheets, but nothing quite fit the bill.
What we saw as the most pressing matter was agreeing on genres. A single album may have as many as 5-6 genres associated with them, and this made it hard to get lists where all albums where listed with the same genres.
Syntax for (complex) band names and album names was also a challenge, but less so.
In the end, I decided to try to build something custom made, and SuShe was born.
In my group of music enthusiasts, we have landed on making [RYM](https://rateyourmusic.com/) our source of truth. We are using the two first listed genres for an album as Genre 1 and Genre 2, respectively. 
Some sites and platforms have also been seen to use different dates for release. RYM is also the master data in this context.


### Disclaimer
**I am not a developer!**
**I can not code!**

All code included in this repo is written by an AI tool on my order.
I understand just enough about coding to understand basic concepts. I also barely know enough to ask an AI for the right thing. It has been a turbulent but effective partnership! :-)


## What SuShe does

Basically, SuShe lets the user search (in the Spotify catalog) for an artist. You can now select an artist, which will list the albums for that artist, including year of release. Double clicking an album will add it to your list, and include the following info:
- Artist name
- Album name
- Date of release
- Cover art

The rest of the table includes columns for the following info to be added manually:
- Country
- Genre 1
- Genre 2
- Rating (0.00 - 5.00)
- Comment

The application stores the users list as a json file. The cover art is included in the json as a base64 encoded string. This was done to consolidate all data in a single file, making it easier for users to move, store or submit their list.
The saved json file will store the albums sorted based on the rating in descending order. It will also store a rank value, deciding the order of the album in the list, and a points value. The points is only relevant if you want to compile some aggregated album of the year list, comprised of lists from multiple users. 

It is also supported to open an album directly from the list, in the preferred player of the user (Spotify or Tidal). If Spotify is selected in settings, this will open the Spotify application and the album directly. 
Since Tidal has (up until recently) been more closed regarding their API, I have not implemented the same integration, but instead opted for creating a URL that will open the Tidal website search, using the artist name and album name as search input. Not very elegant, but it sort of works.

Eventually I aim for SuShe to take advantage of the RYM (Rate Your Music) API once they release that. Currently it is under development and being tested by selected users. [RYM API Announcement](https://rateyourmusic.com/data-access/register-interest/)


## Contribution
Although I am very nervous about letting people see what I feel must be a mess of a project, I am welcoming the opportunity to let others potentially guide me and even contribute directly to the project. Please reach out, and don't be afraid to let me know just how much better something can be done! :-)

## LICENSE
This project is licensed under the GPLv3 license. See LICENSE for details.
Also see LICENSES.md for license details on dependencies.
