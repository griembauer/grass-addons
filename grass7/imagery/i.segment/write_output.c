/* write_output(): transfer the segmented regions from the segmented data file to a raster file */
/* close_files(): close SEG files and free memory */

#include <stdlib.h>
#include <grass/gis.h>
#include <grass/raster.h>
#include <grass/segment.h>	/* segmentation library */
#include "iseg.h"

/* TODO polish: some time delay here with meanbuf, etc being processed.  I only put if statements on the actual files
 * to try and keep the code more clear.  Need to see if this raster makes stats processing easier?  Or IFDEF it out?
 * If it is left in, need to refine it to save a raster for each band in the input group.
 */

int write_output(struct files *files)
{
    int out_fd, mean_fd, row, col;	/* mean_fd for validiating/debug of means */
    CELL *outbuf;
    DCELL *meanbuf;
    struct Colors colors;
	struct History history;


    outbuf = Rast_allocate_c_buf();	/* hold one row of data to put into raster */
    meanbuf = Rast_allocate_d_buf();

    /* force all data to disk */
    segment_flush(&files->bands_seg);
    segment_flush(&files->iseg_seg);

    /* open output raster map */
    G_debug(1, "preparing output raster");
    out_fd = Rast_open_new(files->out_name, CELL_TYPE);
    if (files->out_band != NULL)
	mean_fd = Rast_open_new(files->out_band, DCELL_TYPE);

    /* transfer data from segmentation file to raster */
    for (row = 0; row < files->nrows; row++) {
	Rast_set_c_null_value(outbuf, files->ncols);	/*set buffer to NULLs, only write those that weren't originally masked */
	Rast_set_d_null_value(meanbuf, files->ncols);
	for (col = 0; col < files->ncols; col++) {
	    segment_get(&files->bands_seg, (void *)files->bands_val, row,
			col);
	    if (!(FLAG_GET(files->null_flag, row, col))) {
		segment_get(&files->iseg_seg, &(outbuf[col]), row, col);
		meanbuf[col] = files->bands_val[0];
	    }
	}
	Rast_put_row(out_fd, outbuf, CELL_TYPE);
	if (files->out_band != NULL)
	    Rast_put_row(mean_fd, meanbuf, DCELL_TYPE);

	G_percent(row, files->nrows, 1);
    }

    /* close and save file */
    Rast_close(out_fd);
    if (files->out_band != NULL)
	Rast_close(mean_fd);

    /* set colors */
    Rast_init_colors(&colors);
    Rast_make_random_colors(&colors, 1, files->nrows * files->ncols);	/* TODO polish - number segments from 1 - max ? and then can use that max here. */
    Rast_write_colors(files->out_name, G_mapset(), &colors);

	/* add command line to history */
	/* todo polish, any other information that would be interesting?  Number of passes?  Number of segments made? */
	/* see i.pca as an example of setting custom info */
	Rast_short_history(files->out_name, "raster", &history);
	Rast_command_history(&history);
	Rast_write_history(files->out_name, &history);

    /* free memory */
    G_free(outbuf);
    G_free(meanbuf);
    Rast_free_colors(&colors);

    return TRUE;
}

int close_files(struct files *files)
{

    /* close segmentation files and output raster */
    G_debug(1, "closing bands_seg...");
    segment_close(&files->bands_seg);
    G_debug(1, "closing bounds_seg...");
    if (files->bounds_map != NULL)
	segment_close(&files->bounds_seg);

    G_debug(1, "freeing _val");
    G_free(files->bands_val);
    G_free(files->second_val);

    G_debug(1, "freeing iseg");
    segment_close(&files->iseg_seg);

    G_debug(1, "destroying flags");
    flag_destroy(files->null_flag);
    flag_destroy(files->candidate_flag);
    flag_destroy(files->seeds_flag);

    G_debug(1, "close_files() before link_cleanup()");
    link_cleanup(files->token);
    G_debug(1, "close_files() after link_cleanup()");

    return TRUE;
}
